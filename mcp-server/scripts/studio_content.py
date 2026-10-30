"""Build content for all seven Document Studio templates from the real MCP tools.

Mirrors what Bob does: gather with the read-only tools first, then export.
Used by the sample generator script and by the tests. Uses synthetic demo data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from salesflow_mcp import server as s

ACCOUNT = "Acme Healthcare"
ACCOUNT_ID = "acct_acme_healthcare"


def _transcript() -> str:
    path = Path(s._data_dir()) / "demo_acme_meeting.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    t = raw["transcript"] if isinstance(raw, dict) and "transcript" in raw else raw
    return "\n".join(t) if isinstance(t, list) else str(t)


def _sources(*results: dict) -> list[dict]:
    out = []
    for r in results:
        for src in r.get("sources", []) or []:
            out.append({"source_id": src.get("source_id"), "source_url": src.get("source_url"),
                        "verified_date": src.get("verified_date")})
    return out


def build_all_contents() -> dict[str, dict]:
    """Return {document_type: content} using existing tools only."""
    acct = s.get_account_profile(ACCOUNT)
    opp = s.get_opportunity_context(ACCOUNT_ID)
    risk = s.get_at_risk_deals()
    summary = s.get_pipeline_summary()
    comparison = s.compare_solutions(account_id=ACCOUNT_ID)
    notes = _transcript()
    meeting = s.analyze_meeting_notes(meeting_notes=notes, opportunity_id=opp["data"]["opportunity_id"])
    proposals = s.propose_crm_updates(meeting_notes=notes, account_id=ACCOUNT_ID)
    s.run_pipeline_review()
    digest = s.get_latest_pipeline_digest()

    a, o = acct["data"], opp["data"]
    acme_deals = [d for d in risk["data"]["deals"] if d["opportunity_id"] == o["opportunity_id"]]
    prod = s.search_product_knowledge("storage")
    spin = s.get_sales_playbook("spin")

    brief = {
        "account": {k: a[k] for k in ("account_id", "name", "industry", "overview", "challenges", "unknowns")}
        | {"source_id": acct["sources"][0]["source_id"]},
        "opportunity": {"opportunity_id": o["opportunity_id"], "name": o["name"], "stage": o["stage"],
                        "requirements": o["requirements"], "stakeholders": o["stakeholders"], "notes": o["notes"],
                        "unknowns": o["unknowns"], "source_id": opp["sources"][0]["source_id"]},
        "spin_questions": [
            {"category": "Situation", "question": "How are your storage arrays currently deployed across sites?"},
            {"category": "Problem", "question": "What happened during your last storage outage?"},
            {"category": "Implication", "question": "What does an array failure during clinical hours mean for patient care?"},
            {"category": "Need-Payoff", "question": "How would a non-disruptive migration help your team's timeline?"},
        ],
        "agenda": [
            {"time_slot": "0-5 min", "segment": "Context", "goal": "Confirm objectives for the meeting"},
            {"time_slot": "5-25 min", "segment": "Discovery", "goal": "Understand workloads and the support deadline"},
            {"time_slot": "25-30 min", "segment": "Next steps", "goal": "Agree owners and dates"},
        ],
        "qualification_gaps": [
            {"gap": "Budget not confirmed", "why_it_matters": "Determines which options can be proposed."},
            {"gap": "Decision maker not named", "why_it_matters": "Needed to plan stakeholder engagement."},
        ],
        "next_steps": [{"action": "Schedule a technical deep-dive with the infrastructure team."}],
        "solution_positioning": {
            "products": [
                {"product_id": p.get("product_id", "p"), "name": p["name"], "summary": p.get("summary"),
                 "capabilities": p.get("capabilities", []), "limitations": p.get("limitations", []),
                 "verification_status": p.get("verification_status", "synthetic_unverified"),
                 "source_id": p.get("source_id"), "source_url": p.get("source_url"),
                 "verified_date": p.get("verified_date")}
                for p in prod["data"]["products"][:2]
            ],
            "notice": "Product statements come from catalog text and are not validated configurations.",
        } if prod.get("status") == "ok" and prod["data"].get("products") else None,
        "sources": _sources(acct, opp, prod),
        "playbook_available": spin.get("status") == "ok",
    }
    if brief["solution_positioning"] is None:
        del brief["solution_positioning"]

    cmp_d = comparison["data"]
    return {
        "discovery_brief": brief,
        "account_summary": {
            "account": {k: a[k] for k in ("account_id", "name", "industry", "overview", "challenges", "unknowns")}
            | {"source_id": acct["sources"][0]["source_id"]},
            "opportunities": [{"opportunity_id": o["opportunity_id"], "name": o["name"], "stage": o["stage"],
                               "requirements": o["requirements"], "stakeholders": o["stakeholders"],
                               "unknowns": o["unknowns"], "source_id": opp["sources"][0]["source_id"]}],
            "at_risk_deals": acme_deals,
            "next_steps": ["Confirm budget and decision-maker.", "Schedule the technical deep-dive."],
            "sources": _sources(acct, opp),
        },
        "action_plan": {
            "account_name": ACCOUNT,
            "opportunity": {"opportunity_id": o["opportunity_id"], "name": o["name"], "stage": o["stage"],
                            "requirements": o["requirements"], "stakeholders": o["stakeholders"],
                            "unknowns": o["unknowns"], "source_id": opp["sources"][0]["source_id"]},
            "actions": [
                {"action": "Send a recap and propose dates for the technical deep-dive.", "owner": "Bob",
                 "deadline": "2026-11-05", "basis": "AI recommendation"},
            ],
            "risks": acme_deals,
            "open_questions": ["Which workloads depend on the arrays being replaced?"],
            "crm_updates": proposals["data"]["proposals"]["proposed_updates"][:6],
            "sources": _sources(opp),
        },
        "deal_risk_assessment": {
            "deals": risk["data"]["deals"][:5],
            "pipeline_summary": summary["data"],
            "sources": _sources(risk, summary),
        },
        "solution_comparison": {
            "account_name": ACCOUNT, "opportunity_name": cmp_d.get("opportunity_name"),
            "notice": cmp_d["notice"], "candidates": cmp_d["candidates"],
            "side_by_side": cmp_d["side_by_side"], "comparison_matrix": cmp_d["comparison_matrix"],
            "product_summaries": cmp_d["product_summaries"],
            "requirements_not_yet_validated": cmp_d["requirements_not_yet_validated"],
            "recommended_discovery_questions": cmp_d["recommended_discovery_questions"],
            "preliminary_solution_direction": cmp_d["preliminary_solution_direction"],
            "fit_status_legend": cmp_d["fit_status_legend"],
            "sources": _sources(comparison),
        },
        "followup_plan": {
            "account_name": ACCOUNT, "opportunity_id": o["opportunity_id"],
            "meeting_label": "Discovery call (demo transcript)",
            "meeting_analysis": meeting["data"],
            "crm_proposals": proposals["data"]["proposals"],
            "actions": [{"action": "Email a meeting recap to the Director of Infrastructure.", "owner": "Bob",
                         "deadline": "2026-10-30", "basis": "AI recommendation"}],
        },
        "pipeline_digest": {"digest": digest["data"]["digest"]},
    }
