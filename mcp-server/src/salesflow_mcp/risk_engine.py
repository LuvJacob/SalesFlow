"""Deal Risk Engine for SalesFlow.

Evaluates opportunities against transparent scoring rules to detect risks.
Missing fields are treated as Unknown and do not contribute to risk score.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

log = logging.getLogger(__name__)


def calculate_days_between(date_str1: str, date_str2: str) -> int | None:
    """Calculate date_str1 - date_str2 in days."""
    try:
        d1 = date.fromisoformat(date_str1)
        d2 = date.fromisoformat(date_str2)
        return (d1 - d2).days
    except (ValueError, TypeError):
        return None


def analyze_opportunity_risk(
    opportunity: dict[str, Any],
    account: dict[str, Any] | None = None,
    current_date_str: str = "2026-10-29",
) -> dict[str, Any]:
    """Analyze a single opportunity for pipeline risk.

    Returns a dict with overall risk score, rating, flagged risks, and unknown factors.
    """
    flagged_risks = []
    unknown_factors = []
    total_score = 0

    opp_id = opportunity.get("opportunity_id", "unknown")
    opp_name = opportunity.get("name", "Unnamed Opportunity")
    stage = opportunity.get("stage", "Unknown Stage")
    seller = opportunity.get("seller", "Unknown Seller")
    val = opportunity.get("value", 0.0)

    # Gather unknowns lists
    opp_unknowns = set(opportunity.get("unknowns", []))
    acct_unknowns = set(account.get("unknowns", [])) if account else set()
    combined_unknowns = opp_unknowns | acct_unknowns

    # 1. No recent customer activity
    last_act = opportunity.get("last_activity_days")
    if last_act is None:
        unknown_factors.append("last_activity_days")
    else:
        try:
            last_act_days = int(last_act)
            if last_act_days > 30:
                flagged_risks.append({
                    "factor": "No recent customer activity",
                    "evidence": f"Last customer contact was {last_act_days} days ago",
                    "score_contribution": 3,
                    "recommended_action": "Reach out immediately to reconnect, check-in on project status, or schedule a quick sync.",
                })
                total_score += 3
            elif last_act_days > 14:
                flagged_risks.append({
                    "factor": "No recent customer activity",
                    "evidence": f"Last customer contact was {last_act_days} days ago",
                    "score_contribution": 1,
                    "recommended_action": "Schedule a routine check-in or send a relevant product update to maintain momentum.",
                })
                total_score += 1
        except (ValueError, TypeError):
            unknown_factors.append("last_activity_days")

    # 2. Upcoming or overdue closing dates
    close_dt = opportunity.get("close_date")
    if not close_dt:
        unknown_factors.append("close_date")
    else:
        days_to_close = calculate_days_between(close_dt, current_date_str)
        if days_to_close is None:
            unknown_factors.append("close_date")
        elif days_to_close < 0:
            flagged_risks.append({
                "factor": "Overdue closing date",
                "evidence": f"Target close date ({close_dt}) has passed by {abs(days_to_close)} days",
                "score_contribution": 3,
                "recommended_action": "Update the projected close date in the CRM and confirm the client's current procurement timeline.",
            })
            total_score += 3
        elif days_to_close <= 30:
            flagged_risks.append({
                "factor": "Upcoming closing date",
                "evidence": f"Target close date ({close_dt}) is in {days_to_close} days",
                "score_contribution": 1,
                "recommended_action": "Validate procurement, legal review, and signature steps to ensure timely execution.",
            })
            total_score += 1

    # 3. Missing budget confirmation
    budget_conf = opportunity.get("budget_confirmed")
    is_budget_unknown = "budget" in combined_unknowns or "annual IT budget" in combined_unknowns
    if budget_conf is False or is_budget_unknown:
        flagged_risks.append({
            "factor": "Missing budget confirmation",
            "evidence": "Budget confirmation is missing or listed as an unknown qualification detail.",
            "score_contribution": 3,
            "recommended_action": "Introduce SPIN Need-Payoff and qualification questions to clarify the IT budget envelope and approval steps.",
        })
        total_score += 3
    elif budget_conf is None:
        unknown_factors.append("budget_confirmed")

    # 4. Missing decision-maker
    dm_identified = opportunity.get("decision_maker_identified")
    is_dm_unknown = "decision maker" in combined_unknowns
    if dm_identified is False or is_dm_unknown:
        flagged_risks.append({
            "factor": "Missing decision-maker",
            "evidence": "Decision-maker has not been identified or is listed as an unknown qualification detail.",
            "score_contribution": 3,
            "recommended_action": "Identify the economic buyer and key stakeholders in the purchasing committee and establish engagement.",
        })
        total_score += 3
    elif dm_identified is None:
        unknown_factors.append("decision_maker_identified")

    # 5. Missing next meeting or follow-up
    next_meet = opportunity.get("next_meeting_scheduled")
    if next_meet is False:
        flagged_risks.append({
            "factor": "Missing next meeting",
            "evidence": "No next meeting or follow-up is currently scheduled with the customer.",
            "score_contribution": 1,
            "recommended_action": "Reach out to the customer to schedule the next logical step, such as a technical deep-dive or follow-up session.",
        })
        total_score += 1
    elif next_meet is None:
        unknown_factors.append("next_meeting_scheduled")

    # 6. Unresolved requirements
    unresolved_reqs = opportunity.get("unresolved_requirements")
    if unresolved_reqs is None:
        unknown_factors.append("unresolved_requirements")
    elif len(unresolved_reqs) > 0:
        flagged_risks.append({
            "factor": "Unresolved requirements",
            "evidence": f"Unresolved requirements detected: {', '.join(unresolved_reqs)}",
            "score_contribution": 1,
            "recommended_action": "Clarify requirements through technical discovery and map them to verified product solutions.",
        })
        total_score += 1

    # 7. Stalled opportunity stage
    stalled = opportunity.get("stalled")
    days_in_stg = opportunity.get("days_in_stage")
    if stalled is True:
        flagged_risks.append({
            "factor": "Stalled opportunity stage",
            "evidence": "Opportunity is flagged as stalled in the CRM.",
            "score_contribution": 1,
            "recommended_action": "Review opportunity strategy, offer additional value to the client, or multi-thread the engagement.",
        })
        total_score += 1
    elif days_in_stg is not None:
        try:
            days_in_stg_val = int(days_in_stg)
            if days_in_stg_val > 45:
                flagged_risks.append({
                    "factor": "Stalled opportunity stage",
                    "evidence": f"Opportunity has been in the '{stage}' stage for {days_in_stg_val} days",
                    "score_contribution": 1,
                    "recommended_action": "Review opportunity strategy, offer additional value to the client, or multi-thread the engagement.",
                })
                total_score += 1
        except (ValueError, TypeError):
            unknown_factors.append("days_in_stage")
    else:
        unknown_factors.append("stalled")

    # Overall rating
    if total_score >= 5:
        rating = "High Risk"
    elif total_score >= 2:
        rating = "Medium Risk"
    else:
        rating = "Low Risk"

    return {
        "opportunity_id": opp_id,
        "name": opp_name,
        "stage": stage,
        "seller": seller,
        "value": val,
        "risk_score": total_score,
        "risk_rating": rating,
        "flagged_risks": flagged_risks,
        "unknown_factors": unknown_factors,
        "disclaimer": (
            "Risk scores are calculated based on heuristic rules for prioritization "
            "and do not represent statistically validated statistical or machine learning predictions."
        ),
    }
