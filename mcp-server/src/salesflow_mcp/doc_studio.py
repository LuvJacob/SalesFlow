"""SalesFlow Document Studio: seven professional Word document templates.

Each template takes *structured content that Bob already retrieved* from the
existing MCP tools (CRM, risk engine, meeting analysis, solution comparison,
scheduled digest) and renders it with the shared components in
``doc_components``. This module never fetches data, never calls other tools
and never invents content for optional sections: missing data is shown as
"not provided" or omitted.

Information integrity: every document labels content as Verified, Synthetic
CRM, AI recommendation, Unknown or Unverified spec, carries a source table
and a seller-review disclaimer, and contains no pricing, performance
guarantees or financial projections.

Safety: output is written only inside the resolved outputs/ directory with a
generated ASCII filename and exclusive-create semantics (never overwrites).
"""

from __future__ import annotations

import io
import logging
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from . import doc_components as dc
from .brief_schema import SalesBriefInput
from .docx_generator import _outputs_dir

log = logging.getLogger("salesflow.docstudio")

DOCUMENT_TYPES: dict[str, str] = {
    "discovery_brief": "Discovery Meeting Brief",
    "account_summary": "Executive Account Summary",
    "action_plan": "Opportunity Action Plan",
    "deal_risk_assessment": "Deal Risk Assessment",
    "solution_comparison": "Solution Comparison Report",
    "followup_plan": "Post-Meeting Follow-Up Plan",
    "pipeline_digest": "Weekly Pipeline Risk Digest",
}

MAX_TITLE_LEN = 120
MAX_LIST = 300
LIST_DISPLAY_CAP = 12  # long free-text lists are capped in the document with a note

STANDARD_DISCLAIMER = (
    "Prepared for seller review. This document is formatted for client-ready presentation but has not "
    "been reviewed by a person: check every statement and remove anything unsuitable before sharing it "
    "outside your team. Customer and CRM data shown here is synthetic demonstration data unless a "
    "section states otherwise. Product statements come from catalog text and are not validated "
    "configurations. This document contains no pricing, quotes, performance guarantees or financial "
    "projections. Deal values are CRM records, not forecasts."
)


class DocStudioError(Exception):
    """Raised for invalid input or unsafe output; message is safe to show to users."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Content schemas (lenient: shaped like the existing tool outputs)
# ---------------------------------------------------------------------------

T = Annotated[str, StringConstraints(max_length=4000)]
S = Annotated[str, StringConstraints(max_length=300)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SourceItem(_Base):
    source_id: Optional[S] = None
    source_url: Optional[T] = None
    url: Optional[T] = None
    verified_date: Optional[S] = None
    title: Optional[T] = None
    source_type: Optional[S] = None
    note: Optional[T] = None


class RiskFactor(_Base):
    factor: T
    evidence: Optional[T] = None
    score_contribution: Optional[int] = None
    recommended_action: Optional[T] = None


class RiskDeal(_Base):
    """Accepts both get_at_risk_deals deals and pipeline-digest flagged deals."""

    rank: Optional[int] = None
    opportunity_id: Optional[S] = None
    account_name: Optional[S] = None
    name: Optional[T] = None
    opportunity_name: Optional[T] = None
    stage: Optional[S] = None
    seller: Optional[S] = None
    value: Optional[float] = None
    close_date: Optional[S] = None
    risk_score: Optional[int] = None
    risk_rating: Optional[S] = None
    flagged_risks: list[RiskFactor] = Field(default_factory=list, max_length=MAX_LIST)
    evidence: list[RiskFactor] = Field(default_factory=list, max_length=MAX_LIST)
    recommended_actions: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    unknown_factors: list[S] = Field(default_factory=list, max_length=MAX_LIST)
    disclaimer: Optional[T] = None
    source_id: Optional[S] = None


class ActionItem(_Base):
    action: T
    owner: Optional[S] = None
    deadline: Optional[S] = None
    basis: Optional[S] = None


class _Common(_Base):
    executive_summary: list[T] = Field(default_factory=list, max_length=20)
    unknowns: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    sources: list[SourceItem] = Field(default_factory=list, max_length=MAX_LIST)
    prepared_by: Optional[S] = None
    synthetic: bool = True


class DiscoveryBriefContent(SalesBriefInput):
    """Same structure as the existing discovery brief input, plus optional extras."""

    executive_summary: list[T] = Field(default_factory=list, max_length=20)
    unknowns: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    sources: list[SourceItem] = Field(default_factory=list, max_length=MAX_LIST)  # type: ignore[assignment]
    prepared_by: Optional[S] = None


class OpportunityIn(_Base):
    opportunity_id: Optional[S] = None
    name: Optional[T] = None
    stage: Optional[S] = None
    requirements: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    stakeholders: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    notes: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    unknowns: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    source_id: Optional[S] = None


class AccountIn(_Base):
    account_id: Optional[S] = None
    name: S
    industry: Optional[T] = None
    overview: Optional[T] = None
    challenges: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    unknowns: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    source_id: Optional[S] = None


class AccountSummaryContent(_Common):
    account: AccountIn
    opportunities: list[OpportunityIn] = Field(default_factory=list, max_length=50)
    at_risk_deals: list[RiskDeal] = Field(default_factory=list, max_length=50)
    next_steps: list[T] = Field(default_factory=list, max_length=MAX_LIST)


class CrmUpdate(_Base):
    field: Optional[S] = None
    proposed_value: Optional[Any] = None
    excerpt: Optional[T] = None
    uncertainty: Optional[S] = None
    action: Optional[S] = None


class ActionPlanContent(_Common):
    account_name: S
    opportunity: Optional[OpportunityIn] = None
    actions: list[ActionItem] = Field(default_factory=list, max_length=MAX_LIST)
    risks: list[RiskDeal] = Field(default_factory=list, max_length=50)
    open_questions: list[T] = Field(default_factory=list, max_length=MAX_LIST)
    crm_updates: list[CrmUpdate] = Field(default_factory=list, max_length=MAX_LIST)


class PipelineSummaryIn(_Base):
    total_deals: Optional[int] = None
    total_value: Optional[float] = None
    risk_distribution: dict[str, Any] = Field(default_factory=dict)
    top_risk_factors: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    disclaimer: Optional[T] = None


class DealRiskContent(_Common):
    deals: list[RiskDeal] = Field(..., min_length=1, max_length=50)
    pipeline_summary: Optional[PipelineSummaryIn] = None
    account_name: Optional[S] = None


class ComparisonContent(_Common):
    account_name: Optional[S] = None
    opportunity_name: Optional[T] = None
    notice: Optional[T] = None
    candidates: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    side_by_side: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    comparison_matrix: list[dict[str, Any]] = Field(default_factory=list, max_length=600)
    product_summaries: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    requirements_not_yet_validated: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    recommended_discovery_questions: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    preliminary_solution_direction: Optional[dict[str, Any]] = None
    fit_status_legend: list[S] = Field(default_factory=list, max_length=10)


class MeetingAnalysisIn(_Base):
    requirements: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    challenges: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    stakeholders: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    objections: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    budget_and_timeline: dict[str, Any] = Field(default_factory=dict)
    action_items: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    open_questions: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    injection_warnings: list[Any] = Field(default_factory=list, max_length=50)
    disclaimer: Optional[T] = None


class CrmProposalsIn(_Base):
    newly_confirmed: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    changed_requirements: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_LIST)
    resolved_gaps: list[Any] = Field(default_factory=list, max_length=MAX_LIST)
    potentially_outdated: list[Any] = Field(default_factory=list, max_length=MAX_LIST)
    new_risks: list[Any] = Field(default_factory=list, max_length=MAX_LIST)
    proposed_updates: list[CrmUpdate] = Field(default_factory=list, max_length=MAX_LIST)
    preservation_notice: Optional[T] = None
    disclaimer: Optional[T] = None


class FollowupContent(_Common):
    account_name: S
    opportunity_id: Optional[S] = None
    meeting_label: Optional[T] = None
    meeting_analysis: Optional[MeetingAnalysisIn] = None
    crm_proposals: Optional[CrmProposalsIn] = None
    actions: list[ActionItem] = Field(default_factory=list, max_length=MAX_LIST)


class DigestSummaryIn(_Base):
    active_deals_analyzed: Optional[int] = None
    total_active_value: Optional[float] = None
    flagged_deals: Optional[int] = None
    flagged_value: Optional[float] = None
    risk_distribution: dict[str, Any] = Field(default_factory=dict)
    top_risk_factors: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    unknown_factor_counts: dict[str, Any] = Field(default_factory=dict)


class DigestIn(_Base):
    run_id: Optional[S] = None
    schedule_name: Optional[T] = None
    trigger: Optional[S] = None
    generated_at: Optional[S] = None
    generated_at_local: Optional[S] = None
    timezone: Optional[S] = None
    review_date: Optional[S] = None
    seller_scope: Optional[S] = None
    synthetic_data: Optional[bool] = None
    definitions: dict[str, Any] = Field(default_factory=dict)
    summary: DigestSummaryIn = Field(default_factory=DigestSummaryIn)
    flagged_deals: list[RiskDeal] = Field(default_factory=list, max_length=200)
    not_flagged_opportunity_ids: list[S] = Field(default_factory=list, max_length=500)
    notes: list[T] = Field(default_factory=list, max_length=50)
    disclaimer: Optional[T] = None
    limitations: Optional[T] = None


class PipelineDigestContent(_Common):
    digest: DigestIn


CONTENT_MODELS: dict[str, type[BaseModel]] = {
    "discovery_brief": DiscoveryBriefContent,
    "account_summary": AccountSummaryContent,
    "action_plan": ActionPlanContent,
    "deal_risk_assessment": DealRiskContent,
    "solution_comparison": ComparisonContent,
    "followup_plan": FollowupContent,
    "pipeline_digest": PipelineDigestContent,
}


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------


def _money(v: Optional[float]) -> str:
    return f"${v:,.0f}" if isinstance(v, (int, float)) else "Unknown"


def _readable(key: str) -> str:
    return dc.clean(key).replace("_", " ").strip()


def _txt(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _is_seller_question(text: str) -> bool:
    t = text.strip()
    return t.startswith("Seller:") or t.endswith("?")


def _cap(items: list, n: int = LIST_DISPLAY_CAP) -> tuple[list, int]:
    return items[:n], max(0, len(items) - n)


def _more_note(doc, hidden: int, what: str) -> None:
    if hidden:
        dc.add_text(doc, f"{hidden} more {what} not shown; see the source analysis.", muted=True, italic=True, size=9)


def _deal_title(d: RiskDeal) -> str:
    name = d.opportunity_name or d.name or d.opportunity_id or "Unnamed opportunity"
    return f"{d.account_name}: {name}" if d.account_name and d.account_name not in name else name


def _risk_rows(deals: list[RiskDeal]) -> list[dict]:
    rows = []
    for i, d in enumerate(deals, 1):
        factors = list(d.evidence) + list(d.flagged_risks)
        evidence: list[str] = []
        actions: list[str] = []
        for f in factors:
            pts = f"+{f.score_contribution}" if f.score_contribution is not None else ""
            line = f"{f.factor} ({pts}): {f.evidence}" if pts and f.evidence else (
                f"{f.factor}: {f.evidence}" if f.evidence else f.factor)
            if line not in evidence:
                evidence.append(line)
            if f.recommended_action and f.recommended_action not in actions:
                actions.append(f.recommended_action)
        for a in d.recommended_actions:
            if a not in actions:
                actions.append(a)
        value = f"CRM value {_money(d.value)}" if d.value is not None else ""
        close = f"Close {d.close_date}" if d.close_date else ""
        seller = f"Seller {d.seller}" if d.seller else ""
        extra = " | ".join(x for x in (value, close, seller) if x)
        rows.append({
            "rank": d.rank or i,
            "name": _deal_title(d),
            "stage": d.stage or "Stage unknown",
            "value_text": extra,
            "rating": d.risk_rating or "Unrated",
            "score": d.risk_score,
            "evidence": evidence or ["No risk evidence recorded."],
            "actions": actions or ["No action recorded."],
        })
    return rows


def _derive_sources(explicit: list[SourceItem], refs: list[tuple]) -> list[dict]:
    """Union of seller-supplied sources and ids found in the content, de-duplicated.

    Titles/types are only derived from the id prefix; nothing else is invented.
    """
    out: list[dict] = []
    seen: set = set()

    def add(sid, url, date, title=None, stype=None, note=None):
        key = (sid or "", url or "")
        if key == ("", "") or key in seen:
            return
        seen.add(key)
        s = (sid or "").lower()
        if not stype:
            stype = ("Synthetic CRM" if "_crm_" in s else "Product catalog" if "_prod_" in s
                     else "Playbook" if "playbook" in s else "")
        if not title:
            title = {"Synthetic CRM": "Synthetic CRM record", "Product catalog": "Product catalog entry",
                     "Playbook": "Sales playbook entry"}.get(stype, "")
        n = note or ""
        if date:
            n = (n + "; " if n else "") + f"verified {date}"
        out.append({"source_id": sid or "", "title": title, "url": url or "", "source_type": stype,
                    "note": n})

    for s in explicit:
        add(s.source_id, s.source_url or s.url, s.verified_date, s.title, s.source_type, s.note)
    for r in refs:
        sid, url, date = (list(r) + [None, None])[:3]
        add(sid, url, date)
    return out


# ---------------------------------------------------------------------------
# Shared document frame
# ---------------------------------------------------------------------------


class _Ctx:
    def __init__(self, doc_type: str, title: str, subject: str, now: datetime):
        self.doc_type = doc_type
        self.title = title
        self.subject = subject
        self.now = now
        self.unknowns: list[str] = []
        self.sources: list[dict] = []
        self.disclaimers: list[str] = []
        self.subtitle = ""
        self.labels_used: set[str] = {dc.LABEL_UNKNOWN}


def _frame(ctx: _Ctx, doc, *, metadata: list[tuple[str, str]], metrics: list[tuple[str, Any]],
           key_points: list[str], supplied_summary: list[str], body: Callable[[Any], None],
           synthetic: bool) -> None:
    dc.add_title_block(
        doc, title=ctx.title, subtitle=ctx.subtitle,
        metadata=[("Prepared for", ctx.subject)] + metadata + [
            ("Generated", ctx.now.strftime("%Y-%m-%d %H:%M UTC")),
            ("Data basis", "Synthetic demonstration CRM data" if synthetic else "Seller-supplied data"),
            ("Status", "DRAFT - for seller review before any external use"),
        ])
    dc.add_h1(doc, "Executive summary")
    dc.add_metric_cards(doc, metrics)
    dc.add_bullets(doc, key_points)
    if supplied_summary:
        dc.add_labelled_text(doc, dc.LABEL_AI, "Assistant-written summary based on the data in this document:")
        dc.add_bullets(doc, supplied_summary)
        ctx.labels_used.add(dc.LABEL_AI)
    body(doc)

    unknowns = [u for u in dict.fromkeys(dc.clean(x) for x in ctx.unknowns) if u.strip()]
    dc.add_h1(doc, "Unknown information")
    if unknowns:
        dc.add_labelled_text(doc, dc.LABEL_UNKNOWN, "Items below are not in the data and must be confirmed.")
        dc.add_bullets(doc, unknowns)
    else:
        dc.add_text(doc, "No unknowns were supplied with this document. Absence of a list is not confirmation "
                         "that everything is known.", muted=True, italic=True)

    dc.add_h1(doc, "Information integrity")
    dc.add_text(doc, "Content in this document is tagged so you can tell how far to trust it.")
    dc.add_evidence_legend(doc)

    dc.add_h1(doc, "Sources")
    if ctx.sources:
        dc.add_source_table(doc, ctx.sources)
    else:
        dc.add_not_provided(doc, "Source references")

    dc.add_h1(doc, "Disclaimer")
    dc.add_disclaimer(doc, " ".join([STANDARD_DISCLAIMER] + ctx.disclaimers))


# ---------------------------------------------------------------------------
# Template 1: Discovery Meeting Brief
# ---------------------------------------------------------------------------


def _render_discovery(ctx: _Ctx, doc, c: DiscoveryBriefContent) -> None:
    a, o = c.account, c.opportunity
    ctx.unknowns += list(a.unknowns) + list(o.unknowns) + list(c.unknowns) + [g.gap for g in c.qualification_gaps]
    refs = [(a.source_id, None, None), (o.source_id, None, None)]
    if c.playbook_available and c.playbook_source_id:
        refs.append((c.playbook_source_id, None, None))
    for p in (c.solution_positioning.products if c.solution_positioning else []):
        refs.append((p.source_id, p.source_url, p.verified_date))
    ctx.sources = _derive_sources(c.sources, refs)
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI}

    key = [f"Meeting with {a.name}" + (f" about {o.name}" if o.name else "") +
           (f" (CRM stage: {o.stage})." if o.stage else ".")]
    if c.qualification_gaps:
        key.append(f"{len(c.qualification_gaps)} qualification gap(s) to close in this conversation.")

    def body(doc):
        dc.add_h1(doc, "Account and opportunity")
        dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC if a.synthetic else dc.LABEL_VERIFIED,
                             "Account record from the CRM.")
        dc.add_key_value_table(doc, [("Account", a.name), ("Industry", a.industry or "Unknown"),
                                     ("Opportunity", o.name or o.opportunity_id), ("Stage", o.stage or "Unknown")])
        if a.overview:
            dc.add_text(doc, a.overview)
        if a.challenges:
            dc.add_h2(doc, "Business challenges on record")
            dc.add_bullets(doc, a.challenges)
        if o.requirements:
            dc.add_h2(doc, "Stated requirements")
            dc.add_bullets(doc, o.requirements)
        _stakeholders(doc, o.stakeholders)
        if o.notes:
            dc.add_h2(doc, "Meeting history")
            dc.add_bullets(doc, o.notes)

        if c.agenda:
            dc.add_h1(doc, "Proposed agenda")
            dc.add_labelled_text(doc, dc.LABEL_AI, "Suggested structure; adjust to the customer's time.")
            dc.add_table(doc, ["Time", "Segment", "Goal"],
                         [[x.time_slot, x.segment, x.goal] for x in c.agenda], [1.0, 2.0, 3.9])
        if c.spin_questions:
            dc.add_h1(doc, "Discovery questions (SPIN)")
            dc.add_labelled_text(doc, dc.LABEL_AI, "Suggested questions; the seller chooses what to ask.")
            for cat in ("Situation", "Problem", "Implication", "Need-Payoff"):
                qs = [q.question for q in c.spin_questions if q.category == cat]
                if qs:
                    dc.add_h2(doc, cat)
                    dc.add_bullets(doc, qs, numbered=True)
        sp = c.solution_positioning
        if sp and (sp.products or sp.directional_angle):
            dc.add_h1(doc, "Solution positioning")
            if sp.notice:
                dc.add_text(doc, sp.notice, muted=True, italic=True, size=9.5)
            if sp.directional_angle:
                dc.add_labelled_text(doc, dc.LABEL_AI, sp.directional_angle)
            for p in sp.products:
                verified = p.verification_status == "verified"
                dc.add_h2(doc, p.name)
                dc.add_labelled_text(doc, dc.LABEL_VERIFIED if verified else dc.LABEL_UNVERIFIED,
                                     p.summary or "No summary in catalog entry.")
                ctx.labels_used.add(dc.LABEL_VERIFIED if verified else dc.LABEL_UNVERIFIED)
                if p.capabilities:
                    dc.add_h3(doc, "Documented capabilities")
                    dc.add_bullets(doc, p.capabilities)
                if p.limitations:
                    dc.add_h3(doc, "Limitations")
                    dc.add_bullets(doc, p.limitations)
        if c.qualification_gaps:
            dc.add_h1(doc, "Qualification gaps")
            dc.add_table(doc, ["Gap", "Why it matters"],
                         [[g.gap, g.why_it_matters] for g in c.qualification_gaps], [2.4, 4.5])
        if c.next_steps:
            dc.add_h1(doc, "Suggested next steps")
            dc.add_action_table(doc, [{"action": n.action, "basis": dc.LABEL_AI} for n in c.next_steps])
        if c.methodology_note:
            dc.add_text(doc, c.methodology_note, muted=True, italic=True, size=9)

    _frame(ctx, doc,
           metadata=[("Account", a.name), ("Opportunity", o.opportunity_id)],
           metrics=[("SPIN questions", len(c.spin_questions)), ("Agenda segments", len(c.agenda)),
                    ("Qualification gaps", len(c.qualification_gaps)), ("Unknown items", len(set(ctx.unknowns)))],
           key_points=key, supplied_summary=c.executive_summary, body=body, synthetic=a.synthetic)


def _stakeholders(doc, stakeholders: list[dict], heading: str | None = "Stakeholders") -> None:
    if not stakeholders:
        return
    if heading:
        dc.add_h2(doc, heading)
    rows = []
    for s in stakeholders[:50]:
        rows.append([_txt(s, "role", "role_hint") or "Role unknown", _txt(s, "name") or "Name not confirmed",
                     _txt(s, "notes", "source_sentence") or "-"])
    dc.add_table(doc, ["Role", "Name", "Notes"], rows, [1.8, 1.8, 3.3])


# ---------------------------------------------------------------------------
# Template 2: Executive Account Summary
# ---------------------------------------------------------------------------


def _render_account(ctx: _Ctx, doc, c: AccountSummaryContent) -> None:
    a = c.account
    ctx.unknowns += list(a.unknowns) + list(c.unknowns) + [u for o in c.opportunities for u in o.unknowns]
    refs = [(a.source_id, None, None)] + [(o.source_id, None, None) for o in c.opportunities] + \
           [(d.source_id, None, None) for d in c.at_risk_deals]
    ctx.sources = _derive_sources(c.sources, refs)
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI}
    high = sum(1 for d in c.at_risk_deals if (d.risk_rating or "").startswith("High"))
    key = [f"{a.name}" + (f" operates in {a.industry}." if a.industry else ".")]
    if c.opportunities:
        key.append(f"{len(c.opportunities)} opportunity record(s) on file.")
    if c.at_risk_deals:
        key.append(f"{len(c.at_risk_deals)} deal(s) flagged by the risk engine, {high} rated High Risk.")

    def body(doc):
        dc.add_h1(doc, "Account snapshot")
        dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC if c.synthetic else dc.LABEL_VERIFIED,
                             "Account record from the CRM.")
        dc.add_key_value_table(doc, [("Account", a.name), ("Account ID", a.account_id or "Unknown"),
                                     ("Industry", a.industry or "Unknown")])
        if a.overview:
            dc.add_text(doc, a.overview)
        else:
            dc.add_not_provided(doc, "Account overview")
        if a.challenges:
            dc.add_h2(doc, "Business challenges on record")
            dc.add_bullets(doc, a.challenges)
        if c.opportunities:
            dc.add_h1(doc, "Opportunities")
            dc.add_table(doc, ["Opportunity", "ID", "Stage"],
                         [[o.name or "Unnamed", o.opportunity_id or "Unknown", o.stage or "Unknown"]
                          for o in c.opportunities], [3.6, 1.9, 1.4])
            for o in c.opportunities:
                if o.requirements or o.stakeholders:
                    dc.add_h2(doc, o.name or o.opportunity_id or "Opportunity")
                    if o.requirements:
                        dc.add_h3(doc, "Requirements on record")
                        dc.add_bullets(doc, o.requirements)
                    _stakeholders(doc, o.stakeholders)
        if c.at_risk_deals:
            dc.add_h1(doc, "Risk posture")
            dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC,
                                 "Heuristic risk scores from CRM fields; see the Deal Risk Assessment for detail.")
            dc.add_risk_table(doc, _risk_rows(c.at_risk_deals))
            for d in c.at_risk_deals:
                if d.disclaimer:
                    ctx.disclaimers.append(d.disclaimer)
                    break
        if c.next_steps:
            dc.add_h1(doc, "Recommended next steps")
            dc.add_action_table(doc, [{"action": s, "basis": dc.LABEL_AI} for s in c.next_steps])

    _frame(ctx, doc, metadata=[("Account ID", a.account_id or "")],
           metrics=[("Opportunities", len(c.opportunities)), ("Flagged deals", len(c.at_risk_deals)),
                    ("High risk", high), ("Unknown items", len(set(ctx.unknowns)))],
           key_points=key, supplied_summary=c.executive_summary, body=body, synthetic=c.synthetic)


# ---------------------------------------------------------------------------
# Template 3: Opportunity Action Plan
# ---------------------------------------------------------------------------


def _render_action_plan(ctx: _Ctx, doc, c: ActionPlanContent) -> None:
    o = c.opportunity
    ctx.unknowns += list(c.unknowns) + list(o.unknowns if o else []) + list(c.open_questions)
    refs = ([(o.source_id, None, None)] if o else []) + [(d.source_id, None, None) for d in c.risks]
    ctx.sources = _derive_sources(c.sources, refs)
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI}

    actions = [{"action": a.action, "owner": a.owner, "deadline": a.deadline, "basis": a.basis or dc.LABEL_AI}
               for a in c.actions]
    have = {a["action"] for a in actions}
    for d in c.risks:
        for r in _risk_rows([d])[0]["actions"]:
            if r not in have and r != "No action recorded.":
                have.add(r)
                actions.append({"action": r, "basis": dc.LABEL_AI})
    unowned = sum(1 for a in actions if not a.get("owner"))
    key = [f"{len(actions)} action(s) proposed; {unowned} still need an owner." if actions else
           "No actions were supplied or derivable from the risk data."]
    if o and o.name:
        key.insert(0, f"Plan for {o.name}" + (f" (stage: {o.stage})." if o.stage else "."))

    def body(doc):
        dc.add_h1(doc, "Action plan")
        if actions:
            dc.add_labelled_text(doc, dc.LABEL_AI,
                                 "Actions come from the risk engine and the seller's input. Owners and deadlines "
                                 "are shown only when supplied; otherwise they are marked for the seller to set.")
            dc.add_action_table(doc, actions)
        else:
            dc.add_not_provided(doc, "Action items")
        if c.risks:
            dc.add_h1(doc, "Risks this plan addresses")
            dc.add_risk_table(doc, _risk_rows(c.risks))
        if o:
            if o.requirements:
                dc.add_h1(doc, "Requirements on record")
                dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC, "From the CRM opportunity.")
                dc.add_bullets(doc, o.requirements)
            if o.stakeholders:
                dc.add_h1(doc, "Stakeholders")
                _stakeholders(doc, o.stakeholders, None)
        if c.crm_updates:
            dc.add_h1(doc, "Proposed CRM updates (not applied)")
            _crm_updates_table(doc, c.crm_updates)
        if c.open_questions:
            dc.add_h1(doc, "Open questions")
            dc.add_bullets(doc, c.open_questions)

    _frame(ctx, doc, metadata=[("Opportunity", (o.opportunity_id if o else "") or "")],
           metrics=[("Actions", len(actions)), ("Need an owner", unowned),
                    ("Risks addressed", len(c.risks)), ("Open questions", len(c.open_questions))],
           key_points=key, supplied_summary=c.executive_summary, body=body, synthetic=c.synthetic)


def _crm_updates_table(doc, updates: list[CrmUpdate]) -> None:
    dc.add_text(doc, "These are proposals only. Nothing has been written to the CRM; the seller must approve "
                     "each change.", muted=True, italic=True, size=9.5)
    rows = [[_readable(u.field or "field unknown"),
             "" if u.proposed_value is None else str(u.proposed_value),
             u.uncertainty or "Unknown", u.excerpt or "-"] for u in updates[:50]]
    dc.add_table(doc, ["Field", "Proposed value", "Uncertainty", "Supporting excerpt"], rows,
                 [1.4, 1.5, 1.0, 3.0])


# ---------------------------------------------------------------------------
# Template 4: Deal Risk Assessment
# ---------------------------------------------------------------------------


def _render_risk(ctx: _Ctx, doc, c: DealRiskContent) -> None:
    deals = c.deals
    ctx.unknowns += list(c.unknowns) + [f"{_deal_title(d)}: {_readable(u)}" for d in deals for u in d.unknown_factors]
    ctx.sources = _derive_sources(c.sources, [(d.source_id, None, None) for d in deals])
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI}
    high = sum(1 for d in deals if (d.risk_rating or "").startswith("High"))
    med = sum(1 for d in deals if (d.risk_rating or "").startswith("Medium"))
    total = sum(d.value or 0 for d in deals)
    ordered = sorted(deals, key=lambda d: (-(d.risk_score or 0), -(d.value or 0), d.opportunity_id or ""))
    top = ordered[0]
    key = [f"Highest risk: {_deal_title(top)} ({top.risk_rating or 'Unrated'}"
           + (f", score {top.risk_score}" if top.risk_score is not None else "") + ")."]
    if c.pipeline_summary and c.pipeline_summary.total_deals is not None:
        key.append(f"Portfolio context: {c.pipeline_summary.total_deals} active deal(s) in the pipeline.")
    for d in deals:
        if d.disclaimer:
            ctx.disclaimers.append(d.disclaimer)
            break

    def body(doc):
        dc.add_h1(doc, "Risk ranking")
        dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC,
                             "Scores come from transparent heuristic rules on CRM fields. Evidence is quoted from "
                             "the risk engine; actions are recommendations.")
        dc.add_risk_table(doc, _risk_rows(ordered))
        ps = c.pipeline_summary
        if ps and ps.risk_distribution:
            dc.add_h1(doc, "Pipeline context")
            rows = []
            for k, label in (("high_risk", "High Risk"), ("medium_risk", "Medium Risk"), ("low_risk", "Low Risk")):
                v = ps.risk_distribution.get(k) or {}
                rows.append([label, v.get("count", "Unknown"), _money(v.get("value"))])
            dc.add_table(doc, ["Rating", "Deals", "CRM value"], rows, [2.5, 1.5, 2.9])
            if ps.top_risk_factors:
                dc.add_h2(doc, "Most common risk factors")
                dc.add_bullets(doc, [f"{f.get('factor')}: {f.get('count')} deal(s)" for f in ps.top_risk_factors[:8]])
            if ps.disclaimer:
                ctx.disclaimers.append(ps.disclaimer)
        unk = [(d, u) for d in deals for u in d.unknown_factors]
        if unk:
            dc.add_h1(doc, "Fields missing from the CRM")
            dc.add_labelled_text(doc, dc.LABEL_UNKNOWN,
                                 "Missing fields are not scored as risk; confirm them to firm up the rating.")
            dc.add_bullets(doc, [f"{_deal_title(d)}: {_readable(u)}" for d, u in unk])
        dc.add_h1(doc, "How scores are produced")
        dc.add_bullets(doc, ["Each risk factor adds points; High Risk is 5 or more, Medium Risk is 2 to 4.",
                             "Scores prioritise attention. They are not statistical or machine-learning predictions.",
                             "Missing CRM fields are reported as Unknown and are not treated as negative evidence."])

    _frame(ctx, doc, metadata=[("Account", c.account_name or "")],
           metrics=[("Deals assessed", len(deals)), ("High risk", high), ("Medium risk", med),
                    ("CRM value in scope", _money(total))],
           key_points=key, supplied_summary=c.executive_summary, body=body, synthetic=c.synthetic)


# ---------------------------------------------------------------------------
# Template 5: Solution Comparison Report
# ---------------------------------------------------------------------------

_FIT_ORDER = ["Supported", "Partially supported", "Not supported", "Unknown / insufficient evidence"]


def _render_comparison(ctx: _Ctx, doc, c: ComparisonContent) -> None:
    prods = c.candidates
    names = {p.get("product_id"): p.get("name") or p.get("product_id") or "Product" for p in prods}
    for p in c.product_summaries:
        names.setdefault(p.get("product_id"), p.get("name") or p.get("product_id"))
    order = [p.get("product_id") for p in prods] or list(names)
    refs = [(p.get("source_id"), p.get("source_url"), p.get("verified_date")) for p in prods]
    ctx.sources = _derive_sources(c.sources, refs)
    ctx.unknowns += list(c.unknowns) + [r.get("requirement", "") for r in c.requirements_not_yet_validated]
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI, dc.LABEL_VERIFIED}
    unverified = [p for p in prods if p.get("verification_status") != "verified"]
    if unverified:
        ctx.labels_used.add(dc.LABEL_UNVERIFIED)
    n_req = len(c.side_by_side)
    n_val = len(c.requirements_not_yet_validated)
    if c.notice:
        ctx.disclaimers.append(c.notice)
    key = [f"{len(order)} catalog product(s) compared against {n_req} customer requirement(s)." if n_req else
           f"{len(order)} catalog product(s) listed."]
    key.append("Fit statuses reflect documented catalog text only. Absence of documentation is shown as Unknown, "
               "not as lack of support.")
    if n_val:
        key.append(f"{n_val} requirement(s) are not yet validated by any candidate.")

    def body(doc):
        if c.notice:
            dc.add_text(doc, c.notice, muted=True, italic=True, size=9.5)
        if c.preliminary_solution_direction:
            pd = c.preliminary_solution_direction
            dc.add_h1(doc, "Preliminary direction")
            dc.add_labelled_text(doc, dc.LABEL_AI, str(pd.get("label") or "Preliminary - worth exploring, "
                                                        "not a recommendation or validated fit"))
            dc.add_bullets(doc, [f"{w.get('name')}: {w.get('rationale')}" for w in (pd.get("worth_exploring") or [])
                                 if isinstance(w, dict)])
            if pd.get("caveats"):
                dc.add_h3(doc, "Caveats")
                dc.add_bullets(doc, [str(x) for x in pd["caveats"]])
        if c.side_by_side and order:
            dc.add_h1(doc, "Requirement fit matrix")
            dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC, "Requirements come from the CRM opportunity.")
            rows = []
            for r in c.side_by_side:
                res = r.get("results") or {}
                label = f"{r.get('requirement_id', '')}: {r.get('requirement', '')}".strip(": ")
                rows.append((label, [res.get(pid, "Unknown / insufficient evidence") for pid in order]))
            dc.add_comparison_matrix(doc, row_header="Requirement", columns=[names.get(p, p) for p in order],
                                     rows=rows)
            dc.add_text(doc, "Statuses: " + ", ".join(c.fit_status_legend or _FIT_ORDER) + ".",
                        muted=True, size=9)
        if c.product_summaries:
            dc.add_h1(doc, "Products compared")
            counts = []
            for p in c.product_summaries:
                sc = p.get("status_counts") or {}
                counts.append([p.get("name"), *[sc.get(k, 0) for k in _FIT_ORDER], p.get("verification_status") or "Unknown"])
            dc.add_table(doc, ["Product", "Supported", "Partial", "Not supported", "Unknown", "Catalog entry"],
                         counts, [2.2, 0.9, 0.8, 0.9, 0.9, 1.2])
            for p in c.product_summaries:
                _product_section(ctx, doc, p, c.comparison_matrix)
        if c.requirements_not_yet_validated:
            dc.add_h1(doc, "Requirements not yet validated")
            dc.add_labelled_text(doc, dc.LABEL_UNKNOWN, "No candidate has full documented evidence for these.")
            dc.add_table(doc, ["Requirement", "Best status", "Why"],
                         [[f"{r.get('requirement_id', '')}: {r.get('requirement', '')}", r.get("best_status", "Unknown"),
                           [str(x) for x in (r.get("reasons") or [])[:3]]] for r in c.requirements_not_yet_validated],
                         [2.8, 1.2, 2.9])
        if c.recommended_discovery_questions:
            dc.add_h1(doc, "Recommended discovery questions")
            dc.add_labelled_text(doc, dc.LABEL_AI, "Questions that would close the gaps above.")
            dc.add_bullets(doc, [f"{q.get('question')} ({q.get('related_requirement_id')})" if q.get("related_requirement_id")
                                 else str(q.get("question")) for q in c.recommended_discovery_questions[:30]
                                 if isinstance(q, dict)], numbered=True)

    _frame(ctx, doc, metadata=[("Account", c.account_name or ""), ("Opportunity", c.opportunity_name or "")],
           metrics=[("Products compared", len(order)), ("Requirements", n_req),
                    ("Not yet validated", n_val), ("Unverified entries", len(unverified))],
           key_points=key, supplied_summary=c.executive_summary, body=body, synthetic=c.synthetic)


def _product_section(ctx: _Ctx, doc, p: dict, matrix: list[dict]) -> None:
    dc.add_h2(doc, str(p.get("name") or p.get("product_id") or "Product"))
    verified = p.get("verification_status") == "verified"
    src = p.get("catalog_source") or {}
    dc.add_labelled_text(doc, dc.LABEL_VERIFIED if verified else dc.LABEL_UNVERIFIED,
                         "Catalog entry " + ("verified" + (f" on {src.get('verified_date')}" if src.get("verified_date") else "")
                                             if verified else "is unverified; treat capabilities as placeholders") + ".")
    strengths = [f"{s.get('requirement_id')}: {'; '.join(str(x) for x in s.get('documented_capability') or [])} "
                 f"({s.get('fit_status')})" for s in (p.get("strengths") or []) if isinstance(s, dict)]
    if strengths:
        dc.add_h3(doc, "Documented capabilities matched to requirements")
        dc.add_bullets(doc, strengths)
    for key, head in (("limitations", "Documented limitations"), ("explicit_gaps", "Explicit gaps"),
                      ("conflicts", "Conflicts to resolve"), ("needs_validation", "Needs specialist validation")):
        vals = [x if isinstance(x, str) else (x.get("detail") or x.get("text") or str(x)) for x in (p.get(key) or [])]
        if vals:
            dc.add_h3(doc, head)
            shown, hidden = _cap(vals, 6)
            dc.add_bullets(doc, shown)
            _more_note(doc, hidden, head.lower())


# ---------------------------------------------------------------------------
# Template 6: Post-Meeting Follow-Up Plan
# ---------------------------------------------------------------------------

_BAD_OWNERS = {"that", "this", "it", "we", "they", "there", "which", "who", "i", "you"}


def _conf(item: dict) -> str:
    c = _txt(item, "confidence")
    return c.capitalize() if c else "Unknown"


def _render_followup(ctx: _Ctx, doc, c: FollowupContent) -> None:
    m = c.meeting_analysis
    p = c.crm_proposals
    ctx.unknowns += list(c.unknowns)
    ctx.sources = _derive_sources(c.sources, [])
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI}

    def meeting_items(items: list[dict]) -> list[str]:
        out = []
        for i in items:
            t = _txt(i, "text", "source_sentence")
            if t and not _is_seller_question(t):
                out.append(f"{t} [{_conf(i)}]")
        return out

    actions: list[dict] = [{"action": a.action, "owner": a.owner, "deadline": a.deadline,
                            "basis": a.basis or dc.LABEL_AI} for a in c.actions]
    if m:
        for a in m.action_items:
            t = _txt(a, "text")
            if not t:
                continue
            owner = _txt(a, "owner")
            owner = "" if owner.lower() in _BAD_OWNERS else owner
            actions.append({"action": t, "owner": owner, "deadline": _txt(a, "deadline"),
                            "basis": dc.LABEL_AI})
        if m.budget_and_timeline.get("budget_confirmed") is not True:
            ctx.unknowns.append("Budget has not been confirmed in the meeting notes.")
        for q in m.open_questions:
            t = _txt(q, "text")
            if t and not _is_seller_question(t) or t.endswith("?") and not t.startswith("Seller:"):
                ctx.unknowns.append(t)
    if p:
        ctx.unknowns += [str(x) for x in p.potentially_outdated]
    n_act = len(actions)
    n_upd = len(p.proposed_updates) if p else 0
    reqs = meeting_items(m.requirements) if m else []
    key = [f"Follow-up for {c.account_name}" + (f" ({c.meeting_label})." if c.meeting_label else ".")]
    key.append(f"{n_act} follow-up action(s) identified; {sum(1 for a in actions if not a.get('owner'))} without an owner.")
    if n_upd:
        key.append(f"{n_upd} CRM update(s) proposed for the seller to approve; none have been applied.")
    if m and m.injection_warnings:
        ctx.disclaimers.append("Some meeting text looked like instructions and was ignored as data.")

    def body(doc):
        if m:
            dc.add_h1(doc, "What we heard")
            dc.add_labelled_text(doc, dc.LABEL_AI,
                                 "Extracted from meeting notes by pattern matching. [Explicit] means stated in the "
                                 "notes; [Inferred] means suggested by context. Verify before relying on either.")
            for head, items in (("Requirements", reqs), ("Challenges", meeting_items(m.challenges)),
                                ("Objections and concerns", meeting_items(m.objections))):
                if items:
                    dc.add_h2(doc, head)
                    shown, hidden = _cap(items)
                    dc.add_bullets(doc, shown)
                    _more_note(doc, hidden, head.lower())
            if m.stakeholders:
                _stakeholders(doc, [{"role": _txt(s, "role_hint"), "notes": _txt(s, "source_sentence")}
                                    for s in m.stakeholders[:LIST_DISPLAY_CAP]], "Stakeholders mentioned")
            bt = m.budget_and_timeline
            dc.add_h2(doc, "Budget and timeline")
            dc.add_key_value_table(doc, [
                ("Budget confirmed", "Yes" if bt.get("budget_confirmed") is True else "Not confirmed"),
                ("Budget mentions", [str(x) for x in bt.get("budget_mentions") or []][:4] or "None found"),
                ("Timeline mentions", [str(x) for x in bt.get("timeline_mentions") or []][:4] or "None found"),
                ("Dates found", ", ".join(str(x) for x in bt.get("dates_found") or []) or "None found")])
        else:
            dc.add_h1(doc, "What we heard")
            dc.add_not_provided(doc, "Meeting analysis")
        dc.add_h1(doc, "Follow-up actions")
        if actions:
            dc.add_action_table(doc, actions)
        else:
            dc.add_not_provided(doc, "Follow-up actions")
        if p and p.proposed_updates:
            dc.add_h1(doc, "Proposed CRM updates (not applied)")
            _crm_updates_table(doc, p.proposed_updates)
            if p.preservation_notice:
                dc.add_text(doc, p.preservation_notice, muted=True, italic=True, size=9)
        if p and p.new_risks:
            risks = [str(r) for r in p.new_risks if not _is_seller_question(str(r))]
            if risks:
                dc.add_h1(doc, "New risks raised")
                shown, hidden = _cap(risks, 8)
                dc.add_bullets(doc, shown)
                _more_note(doc, hidden, "risks")
        if m and m.open_questions:
            qs = [_txt(q, "text") for q in m.open_questions if _txt(q, "text").endswith("?") and not _txt(q, "text").startswith("Seller:")]
            if qs:
                dc.add_h1(doc, "Open questions from the customer")
                shown, hidden = _cap(qs)
                dc.add_bullets(doc, shown)
                _more_note(doc, hidden, "questions")
        for src in (m.disclaimer if m else None, p.disclaimer if p else None):
            if src:
                ctx.disclaimers.append(src)

    _frame(ctx, doc, metadata=[("Opportunity", c.opportunity_id or ""), ("Meeting", c.meeting_label or "")],
           metrics=[("Follow-up actions", n_act), ("CRM updates proposed", n_upd),
                    ("Requirements heard", len(reqs)), ("Open unknowns", len(set(ctx.unknowns)))],
           key_points=key, supplied_summary=c.executive_summary, body=body, synthetic=c.synthetic)


# ---------------------------------------------------------------------------
# Template 7: Weekly Pipeline Risk Digest
# ---------------------------------------------------------------------------


def _render_digest(ctx: _Ctx, doc, c: PipelineDigestContent) -> None:
    d = c.digest
    s = d.summary
    ctx.unknowns += list(c.unknowns) + [f"{_deal_title(x)}: {_readable(u)}" for x in d.flagged_deals
                                        for u in x.unknown_factors]
    ctx.sources = _derive_sources(c.sources, [(x.source_id, None, None) for x in d.flagged_deals])
    ctx.labels_used |= {dc.LABEL_SYNTHETIC, dc.LABEL_AI}
    if d.disclaimer:
        ctx.disclaimers.append(d.disclaimer)
    if d.limitations:
        ctx.disclaimers.append(d.limitations)
    high = (s.risk_distribution.get("High Risk") or {}).get("count", 0)
    key = []
    if s.active_deals_analyzed is not None:
        key.append(f"{s.flagged_deals if s.flagged_deals is not None else len(d.flagged_deals)} of "
                   f"{s.active_deals_analyzed} active deal(s) are flagged Medium or High risk.")
    if d.flagged_deals:
        t = d.flagged_deals[0]
        key.append(f"Highest priority: {_deal_title(t)} ({t.risk_rating or 'Unrated'}"
                   + (f", score {t.risk_score}" if t.risk_score is not None else "") + ").")
    else:
        key.append("No deals were flagged in this review.")
    if s.top_risk_factors:
        f0 = s.top_risk_factors[0]
        key.append(f"Most common factor: {f0.get('factor')} ({f0.get('count')} deal(s)).")

    def body(doc):
        dc.add_h1(doc, "Risk distribution")
        dc.add_labelled_text(doc, dc.LABEL_SYNTHETIC if d.synthetic_data is not False else dc.LABEL_VERIFIED,
                             "Computed from the CRM at run time.")
        rows = []
        for rating in ("High Risk", "Medium Risk", "Low Risk"):
            v = s.risk_distribution.get(rating)
            if v:
                rows.append([rating, v.get("count", 0), _money(v.get("value"))])
        if rows:
            dc.add_table(doc, ["Rating", "Deals", "CRM value"], rows, [2.5, 1.5, 2.9])
        if s.top_risk_factors:
            dc.add_h2(doc, "Top risk factors")
            dc.add_table(doc, ["Risk factor", "Deals"],
                         [[f.get("factor"), f.get("count")] for f in s.top_risk_factors[:10]], [5.0, 1.9])
        dc.add_h1(doc, "Flagged deals, highest risk first")
        if d.flagged_deals:
            dc.add_labelled_text(doc, dc.LABEL_AI,
                                 "Actions are recommendations. The seller decides what to do.")
            dc.add_risk_table(doc, _risk_rows(d.flagged_deals))
        else:
            dc.add_text(doc, "No deals met the flagging threshold.", muted=True, italic=True)
        if s.unknown_factor_counts:
            dc.add_h1(doc, "Data gaps")
            dc.add_labelled_text(doc, dc.LABEL_UNKNOWN,
                                 "Missing CRM fields are not scored as risk. Confirming them sharpens the ratings.")
            dc.add_table(doc, ["CRM field", "Deals with this field unknown"],
                         [[_readable(k), v] for k, v in s.unknown_factor_counts.items()], [4.5, 2.4])
        if d.not_flagged_opportunity_ids:
            dc.add_h2(doc, "Not flagged")
            dc.add_text(doc, ", ".join(d.not_flagged_opportunity_ids))
        dc.add_h1(doc, "Method and run details")
        if d.definitions:
            dc.add_bullets(doc, [f"{_readable(k).capitalize()}: {v}" for k, v in d.definitions.items()])
        dc.add_key_value_table(doc, [(k, v) for k, v in (
            ("Run ID", d.run_id), ("Trigger", d.trigger), ("Schedule", d.schedule_name),
            ("Seller scope", d.seller_scope), ("Time zone", d.timezone),
            ("Generated (local)", d.generated_at_local)) if v])
        if d.notes:
            dc.add_bullets(doc, d.notes)

    _frame(ctx, doc,
           metadata=[("Review date", d.review_date or ""), ("Seller scope", d.seller_scope or ""),
                     ("Time zone", d.timezone or "")],
           metrics=[("Active deals", s.active_deals_analyzed if s.active_deals_analyzed is not None else "Unknown"),
                    ("Active value", _money(s.total_active_value)),
                    ("Flagged", s.flagged_deals if s.flagged_deals is not None else len(d.flagged_deals)),
                    ("High risk", high)],
           key_points=key, supplied_summary=c.executive_summary, body=body,
           synthetic=d.synthetic_data is not False and c.synthetic)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_RENDERERS: dict[str, Callable[[_Ctx, Any, Any], None]] = {
    "discovery_brief": _render_discovery,
    "account_summary": _render_account,
    "action_plan": _render_action_plan,
    "deal_risk_assessment": _render_risk,
    "solution_comparison": _render_comparison,
    "followup_plan": _render_followup,
    "pipeline_digest": _render_digest,
}


def _subject(doc_type: str, c: Any) -> str:
    if doc_type == "discovery_brief":
        return c.account.name
    if doc_type == "account_summary":
        return c.account.name
    if doc_type in ("action_plan", "followup_plan"):
        return c.account_name
    if doc_type == "deal_risk_assessment":
        return c.account_name or (_deal_title(c.deals[0]) if len(c.deals) == 1 else "Selected deals")
    if doc_type == "solution_comparison":
        return c.account_name or c.opportunity_name or "Selected opportunity"
    return c.digest.seller_scope or "Active pipeline"


def _slug(text: str, limit: int = 40) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")[:limit].strip("_")
    return slug or "document"


def safe_filename(doc_type: str, subject: str, now: datetime) -> str:
    """ASCII-only, traversal-proof, collision-resistant file name."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return f"{doc_type}_{_slug(subject)}_{stamp}_{secrets.token_hex(4)}.docx"


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(x) for x in err.get("loc", ())) or "content"
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    more = len(exc.errors()) - 5
    msg = "; ".join(parts) + (f"; and {more} more" if more > 0 else "")
    return msg[:500]


def validate_content(doc_type: str, content: Any) -> BaseModel:
    if not isinstance(doc_type, str) or doc_type not in DOCUMENT_TYPES:
        raise DocStudioError("invalid_input", "Unknown document_type. Allowed values: " + ", ".join(DOCUMENT_TYPES) + ".")
    if not isinstance(content, dict):
        raise DocStudioError("invalid_input", "content must be a JSON object.")
    try:
        return CONTENT_MODELS[doc_type].model_validate(content)
    except ValidationError as exc:
        log.error("document content failed validation: type=%s errors=%d", doc_type, exc.error_count())
        raise DocStudioError("invalid_input", f"content failed schema validation: {_validation_message(exc)}")


def build_studio_document(doc_type: str, model: BaseModel, title: Optional[str] = None,
                          now: Optional[datetime] = None):
    """Render the python-docx Document for a validated model (no file I/O)."""
    now = now or datetime.now(tz=timezone.utc)
    subject = dc.clean(_subject(doc_type, model))
    custom = dc.clean(title).strip()[:MAX_TITLE_LEN] if title else ""
    label = DOCUMENT_TYPES[doc_type]
    # Default: the template name is the title and the subject is the subtitle.
    clean_title = custom or label
    ctx = _Ctx(doc_type, clean_title, subject, now)
    ctx.subtitle = f"{label}: {subject}" if custom else subject
    doc = dc.new_document(title=custom or f"{label}: {subject}", header_note="DRAFT - for seller review",
                          footer_note="Synthetic demo data. Review before external use.")
    _RENDERERS[doc_type](ctx, doc, model)
    return doc, subject


def generate_document(doc_type: str, content: Any, title: Optional[str] = None,
                      outputs_dir: Optional[Path] = None, now: Optional[datetime] = None) -> dict:
    """Validate, render and save a document inside outputs/. Returns file facts.

    Raises DocStudioError for invalid input or unsafe/failed output.
    """
    model = validate_content(doc_type, content)
    now = now or datetime.now(tz=timezone.utc)
    try:
        doc, subject = build_studio_document(doc_type, model, title, now)
        buf = io.BytesIO()
        doc.save(buf)
    except DocStudioError:
        raise
    except Exception as exc:
        log.error("document rendering failed: %s", type(exc).__name__, exc_info=True)
        raise DocStudioError("generation_failed", "Document generation failed. No file was written.")

    try:
        base = (outputs_dir if outputs_dir is not None else _outputs_dir())
        base.mkdir(parents=True, exist_ok=True)
        base_resolved = base.resolve()
    except Exception as exc:
        log.error("outputs directory unavailable: %s", type(exc).__name__)
        raise DocStudioError("generation_failed", "Could not resolve the outputs directory.")

    data = buf.getvalue()
    for _ in range(5):
        dest = base / safe_filename(doc_type, subject, now)
        try:
            dest.resolve().relative_to(base_resolved)
        except ValueError:
            raise DocStudioError("invalid_input", "Computed output path is unsafe. No file was written.")
        try:
            with open(dest, "xb") as fh:  # exclusive create: never overwrites
                fh.write(data)
        except FileExistsError:
            continue
        except OSError as exc:
            log.error("could not write document: %s", type(exc).__name__)
            raise DocStudioError("generation_failed", "Could not write the document. No file was written.")
        return {
            "file_path": str(dest),
            "file_name": dest.name,
            "size_bytes": dest.stat().st_size,
            "document_type": doc_type,
            "document_label": DOCUMENT_TYPES[doc_type],
            "subject": subject,
        }
    raise DocStudioError("generation_failed", "Could not allocate a unique file name. No file was written.")
