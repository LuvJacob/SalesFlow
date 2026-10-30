"""SalesFlow Markdown report generator.

Renders concise, seller-ready Markdown reports from structured data already
retrieved by the MCP read tools. Writes to outputs/reports/ only.

Design rules:
- Formats supplied content only; never invents facts, capabilities, or URLs.
- Preserves Mermaid code blocks, evidence labels, and synthetic disclosures.
- Filenames are ASCII-only, collision-resistant, and traversal-proof.
- Never overwrites an existing file.
- Verifies the file exists before reporting success.
- Logs to stderr only (stdout carries the MCP protocol stream).

Report types mirror the Document Studio types:
  discovery_brief, account_summary, action_plan, deal_risk_assessment,
  solution_comparison, followup_plan, pipeline_digest
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("salesflow.md_report")

# ---------------------------------------------------------------------------
# Report type registry
# ---------------------------------------------------------------------------

REPORT_TYPES: dict[str, str] = {
    "discovery_brief": "Discovery Meeting Brief",
    "account_summary": "Executive Account Summary",
    "action_plan": "Opportunity Action Plan",
    "deal_risk_assessment": "Deal Risk Assessment",
    "solution_comparison": "Solution Comparison Report",
    "followup_plan": "Post-Meeting Follow-Up Plan",
    "pipeline_digest": "Pipeline Risk Digest",
}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _reports_dir() -> Path:
    """Resolve outputs/reports/ relative to the repo root.

    Override with SALESFLOW_OUTPUTS_DIR for tests (appends /reports).
    """
    override = os.environ.get("SALESFLOW_OUTPUTS_DIR")
    if override:
        p = Path(override)
        if not p.is_absolute():
            raise ValueError("SALESFLOW_OUTPUTS_DIR must be an absolute path.")
        return p / "reports"
    # mcp-server/src/salesflow_mcp/md_report.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3] / "outputs" / "reports"


def _slug(text: str, limit: int = 40) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")[:limit].strip("_")
    return slug or "report"


def safe_report_filename(report_type: str, subject: str, now: datetime, ext: str = ".md") -> str:
    """Collision-resistant, traversal-proof report filename (ext is a fixed internal constant)."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return f"{report_type}_{_slug(subject)}_{stamp}_{secrets.token_hex(4)}{ext}"


def safe_md_filename(report_type: str, subject: str, now: datetime) -> str:
    """Collision-resistant, traversal-proof Markdown filename."""
    return safe_report_filename(report_type, subject, now, ".md")


def _write_report(content: str, report_type: str, subject: str, now: Optional[datetime] = None,
                  reports_dir: Optional[Path] = None, ext: str = ".md") -> Path:
    """Write content to a new report file. Raises FileExistsError or OSError on failure."""
    now = now or datetime.now(tz=timezone.utc)
    base = reports_dir if reports_dir is not None else _reports_dir()
    base.mkdir(parents=True, exist_ok=True)
    base_resolved = base.resolve()

    for _ in range(5):
        dest = base / safe_report_filename(report_type, subject, now, ext)
        try:
            dest.resolve().relative_to(base_resolved)
        except ValueError:
            raise ValueError("Computed report path is outside the allowed directory.")
        try:
            with open(dest, "x", encoding="utf-8") as fh:
                fh.write(content)
            return dest
        except FileExistsError:
            continue
        except OSError as exc:
            log.error("could not write Markdown report: %s", type(exc).__name__)
            raise
    raise OSError("Could not allocate a unique file name after 5 attempts.")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _money(v: Any) -> str:
    if isinstance(v, (int, float)):
        return f"${v:,.0f}"
    return "Unknown"


def _ts(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M UTC")


def _safe_str(v: Any, fallback: str = "Unknown") -> str:
    s = str(v).strip() if v is not None else ""
    return s if s else fallback


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a compact Markdown table."""
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    head = "| " + " | ".join(headers) + " |"
    body_rows = ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |"
                 for row in rows]
    return "\n".join([head, sep] + body_rows)


def _mermaid_risk_chart(dist: dict) -> str:
    """Render a Mermaid pie chart from risk distribution data."""
    high = (dist.get("high_risk") or dist.get("High Risk") or {}).get("count", 0)
    med = (dist.get("medium_risk") or dist.get("Medium Risk") or {}).get("count", 0)
    low = (dist.get("low_risk") or dist.get("Low Risk") or {}).get("count", 0)
    if high + med + low == 0:
        return ""
    lines = ['```mermaid', 'pie title Deal Risk Distribution']
    if high:
        lines.append(f'    "High Risk" : {high}')
    if med:
        lines.append(f'    "Medium Risk" : {med}')
    if low:
        lines.append(f'    "Low Risk" : {low}')
    lines.append('```')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Template renderers
# ---------------------------------------------------------------------------


def _render_discovery_brief(c: dict, now: datetime) -> tuple[str, str]:
    """Returns (markdown_text, subject_label)."""
    account = c.get("account") or {}
    opp = c.get("opportunity") or {}
    spin = c.get("spin_questions") or []
    agenda = c.get("agenda") or []
    gaps = c.get("qualification_gaps") or []
    products = (c.get("solution_positioning") or {}).get("products") or []
    next_steps = c.get("next_steps") or []
    sources = c.get("sources") or []
    synthetic = c.get("synthetic", True)
    acct_name = _safe_str(account.get("name"), "Unknown Account")

    lines: list[str] = [
        f"# Discovery Meeting Brief: {acct_name}",
        f"*Generated {_ts(now)} · DRAFT – for seller review · {'Synthetic demo data' if synthetic else 'Data from CRM'}*",
        "",
    ]

    # --- Account Snapshot ---
    lines += [
        "## Account Snapshot",
        _md_table(
            ["Field", "Detail"],
            [
                ["Company", acct_name],
                ["Industry", _safe_str(account.get("industry"))],
                ["Opportunity", _safe_str(opp.get("name") or opp.get("opportunity_id"))],
                ["Stage", _safe_str(opp.get("stage"))],
            ],
        ),
        "",
    ]
    if account.get("overview"):
        lines += [account["overview"], ""]

    # --- SPIN Questions (exactly 4 in report: one of each type) ---
    # The brief may contain 6-10; show exactly 4 (one per type) in the report
    spin_types = ["Situation", "Problem", "Implication", "Need-Payoff"]
    selected: list[dict] = []
    for stype in spin_types:
        match = next((q for q in spin if isinstance(q, dict) and q.get("category") == stype), None)
        if match:
            selected.append(match)
        else:
            # Fallback: pull from any remaining questions
            fallback = next((q for q in spin if isinstance(q, dict) and q not in selected), None)
            if fallback:
                selected.append({**fallback, "category": stype})

    if selected:
        lines += ["## Discovery Questions (SPIN)", ""]
        for q in selected:
            cat = _safe_str(q.get("category"))
            qtext = _safe_str(q.get("question") or q.get("text"))
            lines.append(f"**{cat}:** {qtext}  ")
        lines.append("")

    # --- 30-Minute Agenda ---
    if agenda:
        lines += ["## 30-Minute Meeting Agenda", ""]
        rows = [[_safe_str(a.get("time_slot", a.get("time"))), _safe_str(a.get("segment")),
                 _safe_str(a.get("goal", a.get("objective")))] for a in agenda if isinstance(a, dict)]
        if rows:
            lines += [_md_table(["Time", "Topic", "Objective"], rows), ""]

    # --- Qualification Gaps ---
    if gaps:
        lines += ["## Qualification Gaps", ""]
        for g in gaps:
            if isinstance(g, dict):
                gap_label = _safe_str(g.get("gap") or g.get("label"))
                lines.append(f"- **{gap_label} (Unknown)**")
            elif isinstance(g, str):
                lines.append(f"- **{g} (Unknown)**")
        lines.append("")

    # --- Potential IBM Products ---
    if products:
        lines += ["## Potential IBM Products", ""]
        prod_rows = []
        for p in products:
            if not isinstance(p, dict):
                continue
            name = _safe_str(p.get("name"))
            category = _safe_str(p.get("category"), "IBM Storage")
            url = p.get("source_url") or ""
            # Only use documented source URLs; never construct guessed URLs
            if url and isinstance(url, str) and url.startswith("http"):
                link = f"[IBM Product Page]({url})"
            else:
                link = "Link unavailable"
            prod_rows.append([name, category, link])
        if prod_rows:
            lines += [_md_table(["Product", "Product Group", "Official IBM Product Page"], prod_rows), ""]

    # --- Next Steps ---
    if next_steps:
        lines += ["## Next Steps", ""]
        for step in next_steps[:3]:
            if isinstance(step, dict):
                lines.append(f"1. {_safe_str(step.get('action') or step.get('text'))}")
            elif isinstance(step, str):
                lines.append(f"1. {step}")
        lines.append("")

    # --- Sources ---
    lines += [
        "## Sources",
        f"*Data retrieved via SalesFlow MCP tools. {'Synthetic CRM and product data — not real customer or product facts.' if synthetic else 'CRM data is live.'} All content is a draft for seller review.*",
        "",
    ]
    if sources:
        for s in sources[:5]:
            if isinstance(s, dict):
                sid = s.get("source_id") or s.get("id") or ""
                url = s.get("source_url") or s.get("url") or ""
                date = s.get("verified_date") or ""
                if sid:
                    note = f"`{sid}`" + (f" · [link]({url})" if url else "") + (f" · verified {date}" if date else "")
                    lines.append(f"- {note}")

    return "\n".join(lines), acct_name


def _render_pipeline(c: dict, now: datetime) -> tuple[str, str]:
    """Pipeline digest or deal risk assessment."""
    digest = c.get("digest") or {}
    summary = digest.get("summary") or c.get("pipeline_summary") or c.get("summary") or {}
    deals = digest.get("flagged_deals") or c.get("deals") or []
    scope = _safe_str(digest.get("seller_scope") or c.get("seller_scope"), "All sellers")
    generated = digest.get("generated_at") or _ts(now)
    synthetic = c.get("synthetic", True) or digest.get("synthetic_data", True)

    total_deals = summary.get("active_deals_analyzed") or summary.get("total_deals") or 0
    total_value = summary.get("total_active_value") or summary.get("total_value") or 0
    flagged = summary.get("flagged_deals") or len(deals)
    dist = summary.get("risk_distribution") or {}

    lines: list[str] = [
        "# Pipeline Intelligence Report",
        f"*Generated {_ts(now)} · {scope} · {'Synthetic demo data' if synthetic else 'Live CRM data'} · DRAFT*",
        "",
        "## Pipeline Metrics",
        "",
        _md_table(
            ["Metric", "Value"],
            [
                ["Active Deals", str(total_deals)],
                ["Total Pipeline Value", _money(total_value)],
                ["Deals Flagged (Medium/High Risk)", str(flagged)],
                ["High Risk Deals", str((dist.get("high_risk") or dist.get("High Risk") or {}).get("count", 0))],
                ["Medium Risk Deals", str((dist.get("medium_risk") or dist.get("Medium Risk") or {}).get("count", 0))],
                ["Low Risk Deals", str((dist.get("low_risk") or dist.get("Low Risk") or {}).get("count", 0))],
            ],
        ),
        "",
    ]

    # Mermaid diagram - preserved as requested
    chart = _mermaid_risk_chart(dist)
    if chart:
        lines += ["## Risk Distribution", "", chart, ""]

    # Top 3 at-risk deals (table)
    top_deals = sorted(deals, key=lambda d: -(d.get("risk_score") or 0))[:3]
    if top_deals:
        lines += ["## Top At-Risk Opportunities", ""]
        risk_rows = []
        for d in top_deals:
            name = _safe_str(d.get("account_name") or d.get("opportunity_id"))
            opp = _safe_str(d.get("opportunity_name") or d.get("name"), "")
            if opp and opp != name:
                name = f"{name}: {opp}"
            rating = _safe_str(d.get("risk_rating"), "Unrated")
            score = d.get("risk_score", "—")
            stage = _safe_str(d.get("stage"), "Unknown")
            value = _money(d.get("value")) if d.get("value") is not None else "Unknown"
            # Recommended actions (first two)
            flags = d.get("flagged_risks") or d.get("evidence") or []
            actions = []
            for f in flags:
                if isinstance(f, dict) and f.get("recommended_action"):
                    actions.append(f["recommended_action"])
            ext_actions = d.get("recommended_actions") or []
            all_actions = actions + [a for a in ext_actions if a not in actions]
            action_text = " / ".join(all_actions[:2]) if all_actions else "—"
            risk_rows.append([name, f"{rating} ({score})", stage, value, action_text])
        lines += [_md_table(["Opportunity", "Risk", "Stage", "Value", "Recommended Action"], risk_rows), ""]

    # Key priorities (max 3)
    factors = summary.get("top_risk_factors") or []
    if factors:
        lines += ["## Key Seller Priorities", ""]
        for i, f in enumerate(factors[:3], 1):
            fname = _safe_str(f.get("factor") if isinstance(f, dict) else f)
            count = f.get("count", "") if isinstance(f, dict) else ""
            suffix = f" ({count} deal{'s' if count != 1 else ''})" if count else ""
            lines.append(f"{i}. Address **{fname}**{suffix}")
        lines.append("")

    lines += [
        "---",
        "*Risk scores are heuristic-based prioritization tools, not statistically validated predictions. "
        "Missing CRM fields are reported as Unknown and are not scored as negative evidence. "
        f"This digest was stored locally and retrieved on request; no notification was sent. "
        f"Execution timestamp: {generated}*",
        "",
    ]
    return "\n".join(lines), scope


def _render_followup(c: dict, now: datetime) -> tuple[str, str]:
    acct_name = _safe_str(c.get("account_name"), "Unknown Account")
    meeting_label = c.get("meeting_label") or ""
    analysis = c.get("meeting_analysis") or {}
    proposals = (c.get("crm_proposals") or {}).get("proposed_updates") or c.get("crm_proposals") or []
    actions = c.get("actions") or analysis.get("action_items") or []
    unknowns = c.get("unknowns") or []
    exec_summary = c.get("executive_summary") or []
    synthetic = c.get("synthetic", True)

    title = f"Post-Meeting Summary: {acct_name}"
    if meeting_label:
        title += f" — {meeting_label}"

    lines: list[str] = [
        f"# {title}",
        f"*Generated {_ts(now)} · DRAFT — for seller review · Not sent · {'Synthetic demo data' if synthetic else 'Live data'}*",
        "",
    ]

    # Executive summary
    if exec_summary:
        lines += ["## Meeting Summary", ""]
        for s in exec_summary[:4]:
            lines.append(str(s))
        lines.append("")
    elif analysis.get("requirements") or analysis.get("challenges"):
        lines += ["## Meeting Summary", ""]
        reqs = [r.get("text") or r.get("source_sentence", "") for r in (analysis.get("requirements") or [])
                if isinstance(r, dict)]
        if reqs:
            lines.append(f"Key requirement identified: {reqs[0]}")
        lines.append("")

    # Action items table
    if actions:
        lines += ["## Action Items", ""]
        rows = []
        for a in actions[:12]:
            if isinstance(a, dict):
                text = _safe_str(a.get("action") or a.get("text"))
                owner = _safe_str(a.get("owner"), "[Unknown]")
                deadline = _safe_str(a.get("deadline"), "[TBD]")
                conf = _safe_str(a.get("confidence") or a.get("basis"), "")
                rows.append([text, owner, deadline, conf])
            elif isinstance(a, str):
                rows.append([a, "[Unknown]", "[TBD]", ""])
        if rows:
            lines += [_md_table(["Action", "Owner", "Deadline", "Basis"], rows), ""]

    # Follow-up email draft
    lines += [
        "## Follow-Up Email Draft",
        "",
        "**DRAFT - for seller review. Not sent.**",
        "",
        f"Subject: Follow-up from our meeting — {acct_name}",
        "",
        f"Hi [Contact name],",
        "",
        f"Thank you for taking the time to connect on [date].",
        "",
    ]
    reqs = [r for r in (analysis.get("requirements") or []) if isinstance(r, dict) and r.get("text")]
    if reqs:
        lines.append("What we heard:")
        for r in reqs[:3]:
            lines.append(f"- {r['text']}")
        lines.append("")
    lines += [
        "Proposed next steps:",
    ]
    for a in (actions or [])[:2]:
        if isinstance(a, dict):
            text = _safe_str(a.get("action") or a.get("text"))
            lines.append(f"1. {text}")
    lines += [
        "",
        "Please let us know if you have any questions.",
        "",
        "[Your name]",
        "",
        "---",
        "*Seller checklist: confirm names and facts, remove anything unsuitable before sending.*",
        "",
    ]

    # Proposed CRM changes
    if proposals:
        lines += ["## Proposed CRM Changes *(not yet applied — seller must approve)*", ""]
        rows = []
        for p in (proposals if isinstance(proposals, list) else [])[:10]:
            if isinstance(p, dict):
                field = _safe_str(p.get("field") or p.get("name"))
                value = _safe_str(p.get("proposed_value") if "proposed_value" in p else p.get("value"), "—")
                unc = _safe_str(p.get("uncertainty"), "—")
                rows.append([field, str(value)[:60], unc])
        if rows:
            lines += [_md_table(["Field", "Proposed Value", "Uncertainty"], rows), ""]

    # Remaining unknowns as labels
    open_qs = [q.get("text") or str(q) for q in (analysis.get("open_questions") or []) if q]
    all_unknowns = list(unknowns) + open_qs
    if all_unknowns:
        lines += ["## Remaining Unknowns", ""]
        for u in all_unknowns[:8]:
            lines.append(f"- **{_safe_str(u)} (Unknown)**")
        lines.append("")

    return "\n".join(lines), acct_name


def _render_solution_comparison(c: dict, now: datetime) -> tuple[str, str]:
    acct_name = _safe_str(c.get("account_name"), "Unknown Account")
    opp_name = c.get("opportunity_name") or ""
    candidates = c.get("candidates") or []
    side_by_side = c.get("side_by_side") or []
    matrix = c.get("comparison_matrix") or []
    unvalidated = c.get("requirements_not_yet_validated") or []
    direction = c.get("preliminary_solution_direction") or {}
    notice = c.get("notice") or ""
    synthetic = c.get("synthetic", True)
    sources = c.get("sources") or []

    subject = acct_name
    title = f"Solution Comparison: {acct_name}"
    if opp_name:
        title += f" — {opp_name}"

    lines: list[str] = [
        f"# {title}",
        f"*Generated {_ts(now)} · DRAFT — for seller review · {'Synthetic/Illustrative data' if synthetic else 'Live data'}*",
        "",
    ]
    if notice:
        lines += [f"> ⚠️ {notice}", ""]

    # Recommendation summary
    if direction:
        worth = direction.get("worth_exploring") or []
        caveats = direction.get("caveats") or []
        if worth:
            lines += ["## Recommendation Summary", ""]
            for w in worth[:2]:
                if isinstance(w, dict):
                    lines.append(f"- **{_safe_str(w.get('name'))}**: {_safe_str(w.get('rationale', ''))}")
                elif isinstance(w, str):
                    lines.append(f"- {w}")
            if caveats:
                lines.append("")
                for cv in caveats[:3]:
                    lines.append(f"  > *Caveat: {cv}*")
            lines.append("")

    # Comparison matrix
    if side_by_side and candidates:
        prod_ids = [p.get("product_id") for p in candidates]
        prod_names = [_safe_str(p.get("name") or p.get("product_id")) for p in candidates]
        lines += ["## Comparison Matrix", ""]
        rows = []
        for r in side_by_side:
            if not isinstance(r, dict):
                continue
            results = r.get("results") or {}
            req = _safe_str(r.get("requirement") or r.get("requirement_id"))
            row = [req] + [_safe_str(results.get(pid), "Unknown") for pid in prod_ids]
            rows.append(row)
        if rows:
            lines += [_md_table(["Requirement"] + prod_names, rows), ""]

    # Top 2 candidates
    product_summaries = c.get("product_summaries") or []
    top_prods = product_summaries[:2] if product_summaries else candidates[:2]
    if top_prods:
        lines += ["## Top Candidate Products", ""]
        for p in top_prods:
            if not isinstance(p, dict):
                continue
            name = _safe_str(p.get("name") or p.get("product_id"))
            url = p.get("source_url") or (p.get("catalog_source") or {}).get("source_url") or ""
            link = f"[IBM Product Page]({url})" if url and url.startswith("http") else "Link unavailable"
            lines.append(f"### {name}")
            lines.append(f"Official page: {link}")
            # Strengths
            strengths = p.get("strengths") or []
            if strengths:
                lines.append("")
                lines.append("Documented strengths:")
                for s in strengths[:3]:
                    if isinstance(s, dict):
                        lines.append(f"- {_safe_str(s.get('requirement_id'))}: {_safe_str('; '.join(str(x) for x in (s.get('documented_capability') or [])))}")
                    elif isinstance(s, str):
                        lines.append(f"- {s}")
            # Limitations
            lims = p.get("limitations") or []
            if lims:
                lines.append("")
                lines.append("Limitations:")
                for lim in lims[:3]:
                    lines.append(f"- {_safe_str(lim if isinstance(lim, str) else lim.get('detail', str(lim)))}")
            lines.append("")

    # Technical validation gaps
    if unvalidated:
        lines += ["## Technical Validation Gaps", ""]
        for u in unvalidated[:8]:
            if isinstance(u, dict):
                req = _safe_str(u.get("requirement") or u.get("requirement_id"))
                best = _safe_str(u.get("best_status"), "Unknown / insufficient evidence")
                lines.append(f"- **{req}** — {best}")
            elif isinstance(u, str):
                lines.append(f"- **{u} (Unknown)**")
        lines.append("")

    # Sources
    lines += [
        "## Sources",
        f"*{'Fit statuses reflect documented catalog text only. Absence of documentation = Unknown, not lack of support. ' if candidates else ''}"
        f"{'Synthetic/illustrative data — not real product facts. ' if synthetic else ''}Draft for seller review.*",
    ]
    if sources:
        for s in sources[:5]:
            if isinstance(s, dict):
                sid = s.get("source_id") or ""
                url = s.get("source_url") or s.get("url") or ""
                date = s.get("verified_date") or ""
                if sid:
                    note = f"`{sid}`" + (f" · [link]({url})" if url else "") + (f" · verified {date}" if date else "")
                    lines.append(f"- {note}")

    return "\n".join(lines), subject


def _render_digest_report(c: dict, now: datetime) -> tuple[str, str]:
    """Delegates to _render_pipeline for pipeline_digest type."""
    return _render_pipeline(c, now)


def _render_account_summary(c: dict, now: datetime) -> tuple[str, str]:
    account = c.get("account") or {}
    acct_name = _safe_str(account.get("name"), "Unknown Account")
    opps = c.get("opportunities") or []
    at_risk = c.get("at_risk_deals") or []
    exec_summary = c.get("executive_summary") or []
    synthetic = c.get("synthetic", True)

    lines: list[str] = [
        f"# Executive Account Summary: {acct_name}",
        f"*Generated {_ts(now)} · DRAFT — {'Synthetic demo data' if synthetic else 'CRM data'}*",
        "",
    ]
    if account.get("overview"):
        lines += [account["overview"], ""]

    if opps:
        lines += ["## Opportunities", ""]
        rows = [[_safe_str(o.get("name")), _safe_str(o.get("stage")), _safe_str(o.get("opportunity_id"))]
                for o in opps[:10] if isinstance(o, dict)]
        if rows:
            lines += [_md_table(["Opportunity", "Stage", "ID"], rows), ""]

    if at_risk:
        lines += ["## Risk Posture", ""]
        rows = []
        for d in at_risk[:5]:
            if isinstance(d, dict):
                name = _safe_str(d.get("account_name") or d.get("opportunity_id"))
                rating = _safe_str(d.get("risk_rating"), "Unrated")
                score = d.get("risk_score", "—")
                rows.append([name, f"{rating} ({score})"])
        if rows:
            lines += [_md_table(["Opportunity", "Risk Rating"], rows), ""]

    return "\n".join(lines), acct_name


def _render_action_plan(c: dict, now: datetime) -> tuple[str, str]:
    acct_name = _safe_str(c.get("account_name"), "Unknown Account")
    actions = c.get("actions") or []
    risks = c.get("risks") or []
    unknowns = c.get("unknowns") or []
    synthetic = c.get("synthetic", True)

    lines: list[str] = [
        f"# Opportunity Action Plan: {acct_name}",
        f"*Generated {_ts(now)} · DRAFT — {'Synthetic demo data' if synthetic else 'CRM data'}*",
        "",
    ]
    if actions:
        lines += ["## Action Plan", ""]
        rows = []
        for a in actions[:15]:
            if isinstance(a, dict):
                text = _safe_str(a.get("action") or a.get("text"))
                owner = _safe_str(a.get("owner"), "[Unknown]")
                deadline = _safe_str(a.get("deadline"), "[TBD]")
                rows.append([text, owner, deadline])
        if rows:
            lines += [_md_table(["Action", "Owner", "Deadline"], rows), ""]

    if unknowns:
        lines += ["## Open Items", ""]
        for u in unknowns[:8]:
            lines.append(f"- **{_safe_str(u)} (Unknown)**")
        lines.append("")

    return "\n".join(lines), acct_name


# ---------------------------------------------------------------------------
# Renderer registry
# ---------------------------------------------------------------------------

_RENDERERS = {
    "discovery_brief": _render_discovery_brief,
    "account_summary": _render_account_summary,
    "action_plan": _render_action_plan,
    "deal_risk_assessment": _render_pipeline,
    "solution_comparison": _render_solution_comparison,
    "followup_plan": _render_followup,
    "pipeline_digest": _render_digest_report,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class MdReportError(Exception):
    """Safe-to-show error from Markdown report generation."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def save_report(
    report_type: str,
    content: dict,
    *,
    now: Optional[datetime] = None,
    reports_dir: Optional[Path] = None,
) -> dict:
    """Render and save a Markdown report. Returns file facts dict.

    Raises MdReportError for invalid input or I/O failures.
    """
    if report_type not in REPORT_TYPES:
        raise MdReportError("invalid_input", f"report_type must be one of: {', '.join(REPORT_TYPES)}.")
    if not isinstance(content, dict):
        raise MdReportError("invalid_input", "content must be a JSON object.")

    now = now or datetime.now(tz=timezone.utc)
    try:
        renderer = _RENDERERS[report_type]
        md_text, subject = renderer(content, now)
    except MdReportError:
        raise
    except Exception as exc:
        log.error("Markdown rendering failed: %s", type(exc).__name__, exc_info=True)
        raise MdReportError("generation_failed", "Markdown rendering failed. No file was written.")

    try:
        dest = _write_report(md_text, report_type, subject, now, reports_dir)
    except (ValueError, OSError) as exc:
        log.error("Markdown file write failed: %s", type(exc).__name__)
        raise MdReportError("generation_failed", "Could not write the report file.")

    if not dest.exists():
        raise MdReportError("generation_failed", "Report generation reported success but the file was not found.")

    return {
        "file_path": str(dest),
        "file_name": dest.name,
        "size_bytes": dest.stat().st_size,
        "report_type": report_type,
        "report_label": REPORT_TYPES[report_type],
        "subject": subject,
    }
