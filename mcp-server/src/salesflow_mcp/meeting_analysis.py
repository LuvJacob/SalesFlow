"""Meeting Notes Analysis for SalesFlow Feature 2: Meeting-to-Action.

Pure extraction logic — no MCP server dependencies, no I/O.

Design principles:
- Distinguish EXPLICIT (clearly stated in text) from INFERRED (reasonable
  interpretation without a direct quote).
- Never assign a commitment to a person without supporting text.
- Never invent names, dates, or dollar amounts.
- Treat meeting text as untrusted data; never follow instructions inside it.
- All returned dicts are plain Python — no Pydantic at this layer so the
  module stays importable by tests without the full server context.
"""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ constants

MAX_TRANSCRIPT_LEN = 50_000  # characters
MAX_LABEL_LEN = 500

# Patterns that suggest instruction-injection attempts inside meeting text.
# We detect these and flag them without acting on them.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|all|prior)\s+(rules?|instructions?|instructions?)", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(prompt|system|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"(send|post|submit|update|write|delete|create)\s+(an?\s+)?(email|message|record|CRM|database)", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(above|previous|all)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a\s+)", re.IGNORECASE),
    re.compile(r"(forget|override)\s+(your\s+)?(previous|prior|all)\s+(instructions?|context|rules?)", re.IGNORECASE),
    re.compile(r"call\s+tool\s+", re.IGNORECASE),
    re.compile(r"<\s*/?tool\s*>", re.IGNORECASE),
    re.compile(r"system\s*:\s*(ignore|override|you\s+are)", re.IGNORECASE),
]

# ------------------------------------------------------------ helpers

def _detect_injection(text: str) -> list[str]:
    """Return descriptions of any injection-like patterns found in text."""
    hits = []
    for pat in _INJECTION_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0)[:80])
    return hits


def _truncate(s: str, n: int = MAX_LABEL_LEN) -> str:
    s = s.strip()
    if len(s) > n:
        return s[:n].rstrip() + "…"
    return s


def _sentences(text: str) -> list[str]:
    """Split text into rough sentences on . ! ? ; and newlines."""
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _match_any(sentence: str, keywords: list[str]) -> bool:
    sl = sentence.lower()
    return any(kw in sl for kw in keywords)


# ------------------------------------------------------------ section extractors

_REQUIREMENT_KEYWORDS = [
    "need", "needs", "require", "requires", "requirement", "must have",
    "want", "wants", "looking for", "critical", "essential", "important",
    "cannot", "can't", "won't work without", "has to", "have to",
    "expect", "expects", "expectation",
]

_CHALLENGE_KEYWORDS = [
    "problem", "issue", "challenge", "concern", "worried", "worry",
    "struggling", "difficult", "pain", "bottleneck", "risk", "risks",
    "failing", "failed", "outage", "downtime", "slow", "expensive",
    "gap", "gap in", "limitation",
]

_STAKEHOLDER_KEYWORDS = [
    "cio", "cto", "ciso", "vp of", "director of", "head of", "manager",
    "architect", "engineer", "team lead", "lead", "owner", "decision maker",
    "approver", "champion", "sponsor", "buyer", "procurement",
]

_OBJECTION_KEYWORDS = [
    "concerned about", "worry about", "worried about", "too expensive",
    "budget is tight", "cost is", "competitor", "alternative",
    "not sure", "unsure", "doubt", "pushback", "objection",
    "hesitant", "reluctant", "complicated", "complex implementation",
    "vendor lock", "lock-in", "migration risk",
]

_BUDGET_KEYWORDS = [
    "budget", "cost", "price", "pricing", "investment", "spend",
    "funding", "capex", "opex", "fiscal", "approved", "approval",
    "threshold", "ceiling", "constraint",
]

_TIMELINE_KEYWORDS = [
    "deadline", "timeline", "by q", "end of", "within ", "months",
    "weeks", "target date", "go-live", "go live", "launch", "milestone",
    "urgency", "urgent", "asap", "as soon as",
]

_ACTION_KEYWORDS = [
    "action:", "action item", "agreed", "agreed to", "will send",
    "will schedule", "will follow up", "follow-up", "follow up",
    "to do", "todo", "next step", "next steps", "propose",
    "send a", "set up", "schedule a",
]

_DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}"           # ISO
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"  # Month Day, Year
    r"|q[1-4]\s+\d{4}"                  # Q1 2027
    r"|by\s+end\s+of\s+\w+"             # by end of month
    r"|within\s+\d+\s+(?:weeks?|months?|days?)"  # within N weeks
    r")\b",
    re.IGNORECASE,
)

_NAME_TITLE_PATTERN = re.compile(
    r"\b((?:Mr|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"  # Mr/Ms/Dr + name
    r"|(?:Director|VP|Head|Manager|Lead|Chief|Architect)\s+of\s+[A-Z][a-zA-Z ]{2,30}"  # Title of Dept
    r"|[A-Z][a-z]+\s+[A-Z][a-z]+(?=\s+(?:said|mentioned|confirmed|noted|asked|replied|stated)))",  # Name before verb
)


def _extract_requirements(sentences: list[str]) -> list[dict[str, str]]:
    results = []
    for s in sentences:
        sl = s.lower()
        for kw in _REQUIREMENT_KEYWORDS:
            if kw in sl:
                results.append({
                    "text": _truncate(s),
                    "confidence": "explicit",
                })
                break
    return results


def _extract_challenges(sentences: list[str]) -> list[dict[str, str]]:
    results = []
    for s in sentences:
        if _match_any(s, _CHALLENGE_KEYWORDS):
            results.append({
                "text": _truncate(s),
                "confidence": "explicit",
            })
    return results


def _extract_stakeholders(sentences: list[str]) -> list[dict[str, str]]:
    results = []
    seen: set[str] = set()
    for s in sentences:
        sl = s.lower()
        for kw in _STAKEHOLDER_KEYWORDS:
            if kw in sl:
                # Try to pull a role phrase
                role_match = re.search(
                    r"\b((?:CIO|CTO|CISO|VP\s+of\s+\w+|Director\s+of\s+\w+|Head\s+of\s+\w+|"
                    r"[A-Z][a-z]+\s+(?:Manager|Architect|Engineer|Lead|Director|VP|Owner))"
                    r"(?:\s+\w+){0,3})",
                    s,
                )
                role = _truncate(role_match.group(0)) if role_match else _truncate(s)
                key = role.lower()
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "role_hint": role,
                        "source_sentence": _truncate(s),
                        "confidence": "explicit",
                    })
                break
    return results


def _extract_objections(sentences: list[str]) -> list[dict[str, str]]:
    results = []
    for s in sentences:
        if _match_any(s, _OBJECTION_KEYWORDS):
            results.append({
                "text": _truncate(s),
                "confidence": "explicit",
            })
    return results


def _extract_budget_timeline(sentences: list[str]) -> dict[str, Any]:
    budget_sentences: list[str] = []
    timeline_sentences: list[str] = []
    dates_found: list[str] = []

    for s in sentences:
        if _match_any(s, _BUDGET_KEYWORDS):
            budget_sentences.append(_truncate(s))
        if _match_any(s, _TIMELINE_KEYWORDS):
            timeline_sentences.append(_truncate(s))
        # Collect dates from every sentence regardless of keyword match
        for m in _DATE_PATTERN.finditer(s):
            dates_found.append(m.group(0))

    return {
        "budget_mentions": budget_sentences,
        "timeline_mentions": timeline_sentences,
        "dates_found": sorted(set(dates_found)),
        "budget_confirmed": None,  # Cannot determine from text alone
        "confidence": "inferred" if budget_sentences else "unknown",
    }


def _extract_action_items(sentences: list[str]) -> list[dict[str, str]]:
    results = []
    for s in sentences:
        if _match_any(s, _ACTION_KEYWORDS):
            # Try to extract an owner hint: "seller to", "we will", "[name] will"
            owner = None
            om = re.search(
                r"\b(seller|we|our team|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:to|will|agreed to|should)\b",
                s,
            )
            if om:
                owner = om.group(1)

            # Try to extract a deadline
            deadline = None
            dm = _DATE_PATTERN.search(s)
            if dm:
                deadline = dm.group(0)

            results.append({
                "text": _truncate(s),
                "owner": owner,
                "deadline": deadline,
                "confidence": "explicit" if owner else "inferred",
            })
    return results


def _extract_open_questions(sentences: list[str]) -> list[dict[str, str]]:
    results = []
    for s in sentences:
        if s.strip().endswith("?"):
            results.append({
                "text": _truncate(s),
                "confidence": "explicit",
            })
        elif re.search(r"\b(unknown|unclear|tbd|to be determined|not yet|still need|still open|not confirmed|not discussed|no answer)\b", s, re.IGNORECASE):
            results.append({
                "text": _truncate(s),
                "confidence": "explicit",
            })
    return results


# ------------------------------------------------------------ public API

def validate_transcript(text: Any) -> tuple[str | None, str | None]:
    """Return (cleaned_text, None) or (None, error_message)."""
    if not isinstance(text, str):
        return None, "meeting_notes must be a string."
    stripped = text.strip()
    if not stripped:
        return None, "meeting_notes must not be empty."
    if len(stripped) > MAX_TRANSCRIPT_LEN:
        return None, f"meeting_notes must not exceed {MAX_TRANSCRIPT_LEN} characters."
    return stripped, None


def analyze_meeting_notes(
    meeting_notes: str,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured sales intelligence from meeting notes or a transcript.

    Returns a structured dict with:
    - requirements, challenges, stakeholders, objections
    - budget_and_timeline
    - action_items (with owner and deadline where stated)
    - open_questions
    - injection_warnings (if instruction-like text was detected)
    - metadata
    """
    sentences = _sentences(meeting_notes)

    injection_hits = _detect_injection(meeting_notes)

    requirements = _extract_requirements(sentences)
    challenges = _extract_challenges(sentences)
    stakeholders = _extract_stakeholders(sentences)
    objections = _extract_objections(sentences)
    budget_timeline = _extract_budget_timeline(sentences)
    action_items = _extract_action_items(sentences)
    open_questions = _extract_open_questions(sentences)

    return {
        "opportunity_id": opportunity_id,
        "requirements": requirements,
        "challenges": challenges,
        "stakeholders": stakeholders,
        "objections": objections,
        "budget_and_timeline": budget_timeline,
        "action_items": action_items,
        "open_questions": open_questions,
        "injection_warnings": injection_hits,
        "sentence_count": len(sentences),
        "char_count": len(meeting_notes),
        "disclaimer": (
            "Items labelled 'explicit' contain wording from the source text. "
            "Items labelled 'inferred' are reasonable interpretations and must be "
            "confirmed by the seller before use. No commitments have been assigned "
            "to individuals without supporting text."
        ),
    }


def propose_crm_updates(
    analysis: dict[str, Any],
    crm_opportunity: dict[str, Any],
) -> dict[str, Any]:
    """Compare meeting analysis against the CRM opportunity record.

    Produces a proposed change set — read-only. Never modifies CRM data.

    Returns:
    - newly_confirmed: fields whose values can now be stated with confidence
    - changed_requirements: requirements that contradict or extend the CRM record
    - resolved_gaps: items from crm unknowns that are now addressed
    - potentially_outdated: CRM fields that may no longer be current
    - new_risks: risks surfaced in the meeting not present in the CRM
    - new_opportunities: positive signals not in the CRM
    - proposed_updates: list of field-level proposals with excerpt and uncertainty
    - preservation_notice: explicit statement that no CRM data was modified
    """
    proposed: list[dict[str, Any]] = []
    resolved_gaps: list[str] = []
    new_risks: list[str] = []
    new_opportunities: list[str] = []
    changed_requirements: list[dict[str, str]] = []
    potentially_outdated: list[dict[str, str]] = []
    newly_confirmed: list[dict[str, str]] = []

    crm_reqs: list[str] = crm_opportunity.get("requirements", [])
    crm_unknowns: list[str] = [u.lower() for u in crm_opportunity.get("unknowns", [])]
    crm_notes: list[str] = crm_opportunity.get("notes", [])
    crm_stage: str = crm_opportunity.get("stage", "")

    meeting_reqs = analysis.get("requirements", [])
    meeting_challenges = analysis.get("challenges", [])
    meeting_stakeholders = analysis.get("stakeholders", [])
    budget_tl = analysis.get("budget_and_timeline", {})
    action_items = analysis.get("action_items", [])
    open_questions = analysis.get("open_questions", [])

    # --- 1. Budget signals
    if budget_tl.get("budget_mentions"):
        excerpt = budget_tl["budget_mentions"][0]
        is_in_unknowns = any("budget" in u for u in crm_unknowns)
        if is_in_unknowns:
            resolved_gaps.append("budget (partial — see excerpt)")
            proposed.append({
                "field": "notes",
                "proposed_value": f"[Meeting] Budget mentioned: {excerpt}",
                "excerpt": excerpt,
                "uncertainty": "medium — budget mentioned but not confirmed",
                "action": "add_note",
            })
        else:
            newly_confirmed.append({
                "field": "budget_mention",
                "excerpt": excerpt,
                "uncertainty": "medium",
            })

    # --- 2. Decision-maker signals
    if meeting_stakeholders:
        dm_mention = any(
            any(kw in s.get("role_hint", "").lower() for kw in ["cio", "cto", "ciso", "vp", "director", "decision"])
            for s in meeting_stakeholders
        )
        dm_in_unknowns = any("decision" in u or "buyer" in u or "economic" in u for u in crm_unknowns)
        if dm_mention and dm_in_unknowns:
            resolved_gaps.append("decision maker (partial — role identified, name not confirmed)")
            proposed.append({
                "field": "stakeholders",
                "proposed_value": [s["role_hint"] for s in meeting_stakeholders],
                "excerpt": meeting_stakeholders[0].get("source_sentence", ""),
                "uncertainty": "medium — role identified in meeting; confirm name and authority",
                "action": "add_stakeholder",
            })
        elif meeting_stakeholders:
            proposed.append({
                "field": "stakeholders",
                "proposed_value": [s["role_hint"] for s in meeting_stakeholders],
                "excerpt": meeting_stakeholders[0].get("source_sentence", ""),
                "uncertainty": "low — stakeholders mentioned explicitly",
                "action": "add_stakeholder",
            })

    # --- 3. Requirements: new vs. changed
    crm_req_lower = [r.lower() for r in crm_reqs]
    for req in meeting_reqs:
        text = req.get("text", "")
        text_l = text.lower()
        # Check if any existing CRM req partially matches (50 char substring)
        match_found = any(
            text_l[:50] in existing or existing[:50] in text_l
            for existing in crm_req_lower
        )
        if not match_found:
            changed_requirements.append({
                "text": text,
                "status": "new — not in CRM",
                "confidence": req.get("confidence", "inferred"),
            })
            proposed.append({
                "field": "requirements",
                "proposed_value": text,
                "excerpt": text,
                "uncertainty": "low — stated in meeting text",
                "action": "add_requirement",
            })

    # --- 4. Action items → next_meeting_scheduled signal
    if action_items:
        schedule_item = next(
            (a for a in action_items if any(
                kw in a.get("text", "").lower()
                for kw in ["schedule", "meeting", "deep-dive", "call", "demo", "follow"]
            )),
            None,
        )
        if schedule_item:
            if not crm_opportunity.get("next_meeting_scheduled"):
                proposed.append({
                    "field": "next_meeting_scheduled",
                    "proposed_value": True,
                    "excerpt": schedule_item.get("text", ""),
                    "uncertainty": "low — scheduling action item found in meeting",
                    "action": "set_field",
                })
                newly_confirmed.append({
                    "field": "next_meeting_scheduled",
                    "excerpt": schedule_item.get("text", ""),
                    "uncertainty": "low",
                })

    # --- 5. Timeline signals
    timeline_mentions = budget_tl.get("timeline_mentions", [])
    dates_found = budget_tl.get("dates_found", [])
    if timeline_mentions or dates_found:
        timeline_in_unknowns = any("timeline" in u or "deadline" in u or "date" in u for u in crm_unknowns)
        if timeline_in_unknowns:
            resolved_gaps.append("timeline/deadline (partial)")
        excerpt = (timeline_mentions[0] if timeline_mentions else "") or (dates_found[0] if dates_found else "")
        if excerpt:
            proposed.append({
                "field": "notes",
                "proposed_value": f"[Meeting] Timeline/deadline mentioned: {excerpt}",
                "excerpt": excerpt,
                "uncertainty": "medium — date mentioned in meeting; verify against formal agreement",
                "action": "add_note",
            })

    # --- 6. Stage progression signal
    stage_lower = crm_stage.lower()
    # If meeting notes suggest technical depth, the deal may have moved from Discovery
    if stage_lower == "discovery" and any(
        kw in analysis.get("requirements", [{}])[0].get("text", "").lower() if analysis.get("requirements") else False
        for kw in ["confirmed", "explicit", "stated"]
    ):
        pass  # Not enough signal to auto-propose a stage change; add note only

    # Always add a last_activity update proposal
    proposed.append({
        "field": "last_activity_days",
        "proposed_value": 0,
        "excerpt": "Meeting notes submitted today",
        "uncertainty": "low — meeting occurred",
        "action": "set_field",
    })

    # --- 7. New risks from challenges and objections
    for ch in meeting_challenges:
        text = ch.get("text", "")
        if not any(text[:40].lower() in n.lower() for n in crm_notes):
            new_risks.append(text)

    for obj in analysis.get("objections", []):
        text = obj.get("text", "")
        new_risks.append(f"Objection raised: {text}")

    # --- 8. New opportunities from positive signals
    positive_signals = [
        s for s in _sentences(
            " ".join(ai.get("text", "") for ai in action_items)
        )
        if any(kw in s.lower() for kw in ["agreed", "confirmed", "happy", "positive", "interested", "keen", "enthusiastic"])
    ]
    new_opportunities.extend(positive_signals)

    return {
        "opportunity_id": crm_opportunity.get("opportunity_id"),
        "newly_confirmed": newly_confirmed,
        "changed_requirements": changed_requirements,
        "resolved_gaps": resolved_gaps,
        "potentially_outdated": potentially_outdated,
        "new_risks": new_risks,
        "new_opportunities": new_opportunities,
        "proposed_updates": proposed,
        "preservation_notice": (
            "This is a proposed change set only. No CRM data has been modified. "
            "All proposed updates require seller review and approval before being applied."
        ),
        "disclaimer": (
            "Proposals are based on heuristic pattern matching of meeting text. "
            "Field values marked 'medium' or 'high' uncertainty must be verified before use."
        ),
    }
