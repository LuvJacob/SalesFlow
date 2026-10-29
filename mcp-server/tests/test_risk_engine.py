"""Tests for SalesFlow Feature 1: Deal Intelligence & Risk Detection.

Covers:
- Deal Risk Engine python module directly
- MCP tools get_at_risk_deals and get_pipeline_summary
- Various deal risk profiles (healthy, inactive, overdue, sparse, etc.)
- Filtering and error handling
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure the package is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastmcp import Client
from salesflow_mcp.server import mcp
from salesflow_mcp.risk_engine import analyze_opportunity_risk

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "", label: str = "PASS") -> None:
    results.append((name, label if ok else "FAIL", detail))


async def call(client: Client, tool: str, args: dict) -> dict:
    res = await client.call_tool(tool, args, raise_on_error=False)
    if res.structured_content is not None:
        return res.structured_content
    return json.loads(res.content[0].text)


async def main() -> None:
    # 1. Test Deal Risk Engine directly with unit data
    # Scenario A: Healthy Opportunity
    opp_healthy = {
        "opportunity_id": "opp_test_healthy",
        "name": "Healthy Deal",
        "stage": "Proposal",
        "seller": "Alice",
        "value": 100000.0,
        "last_activity_days": 2,
        "close_date": "2026-11-30",
        "budget_confirmed": True,
        "decision_maker_identified": True,
        "next_meeting_scheduled": True,
        "stalled": False,
        "days_in_stage": 5,
        "unresolved_requirements": [],
        "unknowns": []
    }
    analysis_healthy = analyze_opportunity_risk(opp_healthy, current_date_str="2026-10-29")
    record(
        "engine healthy opportunity",
        analysis_healthy["risk_score"] == 0
        and analysis_healthy["risk_rating"] == "Low Risk"
        and len(analysis_healthy["flagged_risks"]) == 0
        and "disclaimer" in analysis_healthy,
        f"score={analysis_healthy['risk_score']} rating={analysis_healthy['risk_rating']}"
    )

    # Scenario B: Inactive Deal
    opp_inactive = {
        "opportunity_id": "opp_test_inactive",
        "name": "Inactive Deal",
        "stage": "Discovery",
        "seller": "Bob",
        "value": 50000.0,
        "last_activity_days": 45,  # >30 (adds 3 points)
        "close_date": "2026-12-15",
        "budget_confirmed": True,
        "decision_maker_identified": True,
        "next_meeting_scheduled": False,  # False (adds 1 point)
        "stalled": True,  # True (adds 1 point)
        "days_in_stage": 60,
        "unresolved_requirements": []
    }
    analysis_inactive = analyze_opportunity_risk(opp_inactive, current_date_str="2026-10-29")
    record(
        "engine inactive deal",
        analysis_inactive["risk_score"] == 5  # 3 + 1 + 1
        and analysis_inactive["risk_rating"] == "High Risk"
        and len(analysis_inactive["flagged_risks"]) == 3,
        f"score={analysis_inactive['risk_score']} rating={analysis_inactive['risk_rating']} risks={[r['factor'] for r in analysis_inactive['flagged_risks']]}"
    )

    # Scenario C: Overdue Close Date
    opp_overdue = {
        "opportunity_id": "opp_test_overdue",
        "name": "Overdue Deal",
        "stage": "Negotiation",
        "seller": "Alice",
        "value": 150000.0,
        "last_activity_days": 5,
        "close_date": "2026-10-15",  # Past date (adds 3 points)
        "budget_confirmed": True,
        "decision_maker_identified": True,
        "next_meeting_scheduled": True,
        "stalled": False,
        "days_in_stage": 10,
        "unresolved_requirements": []
    }
    analysis_overdue = analyze_opportunity_risk(opp_overdue, current_date_str="2026-10-29")
    record(
        "engine overdue close date",
        analysis_overdue["risk_score"] == 3
        and analysis_overdue["risk_rating"] == "Medium Risk"
        and analysis_overdue["flagged_risks"][0]["factor"] == "Overdue closing date",
        f"score={analysis_overdue['risk_score']} rating={analysis_overdue['risk_rating']}"
    )

    # Scenario D: Missing qualification information (treated as Unknown, no risk points)
    opp_sparse = {
        "opportunity_id": "opp_test_sparse",
        "name": "Sparse Deal",
        "stage": "Qualification",
        "seller": "Charlie",
        "value": 30000.0,
        "last_activity_days": 4,
        "close_date": "2026-12-10",
        "budget_confirmed": None,  # Unknown
        "decision_maker_identified": None,  # Unknown
        "next_meeting_scheduled": True,
        "stalled": False,
        "days_in_stage": 3,
        "unresolved_requirements": [],
        "unknowns": []
    }
    analysis_sparse = analyze_opportunity_risk(opp_sparse, current_date_str="2026-10-29")
    record(
        "engine missing qualification (unknown)",
        analysis_sparse["risk_score"] == 0
        and analysis_sparse["risk_rating"] == "Low Risk"
        and "budget_confirmed" in analysis_sparse["unknown_factors"]
        and "decision_maker_identified" in analysis_sparse["unknown_factors"],
        f"score={analysis_sparse['risk_score']} rating={analysis_sparse['risk_rating']} unknowns={analysis_sparse['unknown_factors']}"
    )

    # Scenario E: Sparse Deal with explicit unknowns (treated as High Risk)
    opp_sparse_risks = {
        "opportunity_id": "opp_test_sparse_risks",
        "name": "Sparse Deal with Unknowns",
        "stage": "Qualification",
        "seller": "Charlie",
        "value": 30000.0,
        "last_activity_days": 4,
        "close_date": "2026-12-10",
        "budget_confirmed": None,
        "decision_maker_identified": None,
        "next_meeting_scheduled": True,
        "stalled": False,
        "days_in_stage": 3,
        "unresolved_requirements": [],
        "unknowns": ["budget", "decision maker"]
    }
    analysis_sparse_risks = analyze_opportunity_risk(opp_sparse_risks, current_date_str="2026-10-29")
    record(
        "engine missing qualification with risks",
        analysis_sparse_risks["risk_score"] == 6
        and analysis_sparse_risks["risk_rating"] == "High Risk"
        and len(analysis_sparse_risks["flagged_risks"]) == 2,
        f"score={analysis_sparse_risks['risk_score']} rating={analysis_sparse_risks['risk_rating']}"
    )

    # 2. Test MCP tools end-to-end using the local mock CRM client
    async with Client(mcp) as c:
        # Test get_at_risk_deals
        r = await call(c, "get_at_risk_deals", {})
        record(
            "mcp get_at_risk_deals",
            r["status"] == "ok"
            and isinstance(r["data"]["deals"], list)
            and r["data"]["count"] == 5  # We have 5 mock opportunities in our opportunities.json
            and r["data"]["deals"][0]["risk_score"] >= r["data"]["deals"][-1]["risk_score"],  # Sorted desc
            f"count={r['data']['count']} highest_score={r['data']['deals'][0]['risk_score']} lowest_score={r['data']['deals'][-1]['risk_score']}"
        )

        # Test get_at_risk_deals with filtering
        r_filtered = await call(c, "get_at_risk_deals", {"seller": "Alice"})
        record(
            "mcp get_at_risk_deals filter by seller",
            r_filtered["status"] == "ok"
            and all(d["seller"] == "Alice" for d in r_filtered["data"]["deals"]),
            f"count={r_filtered['data']['count']} sellers={[d['seller'] for d in r_filtered['data']['deals']]}"
        )

        r_stg_filtered = await call(c, "get_at_risk_deals", {"stage": "Discovery"})
        record(
            "mcp get_at_risk_deals filter by stage",
            r_stg_filtered["status"] == "ok"
            and all(d["stage"] == "Discovery" for d in r_stg_filtered["data"]["deals"]),
            f"count={r_stg_filtered['data']['count']} stages={[d['stage'] for d in r_stg_filtered['data']['deals']]}"
        )

        r_risk_filtered = await call(c, "get_at_risk_deals", {"risk_category": "High Risk"})
        record(
            "mcp get_at_risk_deals filter by risk_category",
            r_risk_filtered["status"] == "ok"
            and all(d["risk_rating"] == "High Risk" for d in r_risk_filtered["data"]["deals"]),
            f"count={r_risk_filtered['data']['count']} ratings={[d['risk_rating'] for d in r_risk_filtered['data']['deals']]}"
        )

        # Test get_pipeline_summary
        r_summary = await call(c, "get_pipeline_summary", {})
        record(
            "mcp get_pipeline_summary",
            r_summary["status"] == "ok"
            and r_summary["data"]["total_deals"] == 5
            and r_summary["data"]["total_value"] == 1050000.0  # 150k + 250k + 180k + 420k + 50k
            and "risk_distribution" in r_summary["data"]
            and r_summary["data"]["risk_distribution"]["high_risk"]["count"] >= 1
            and len(r_summary["data"]["top_risk_factors"]) > 0,
            f"deals={r_summary['data']['total_deals']} value={r_summary['data']['total_value']} top_factors={r_summary['data']['top_risk_factors'][:3]}"
        )

        # Test get_pipeline_summary with filter
        r_summary_filtered = await call(c, "get_pipeline_summary", {"seller": "Bob"})
        record(
            "mcp get_pipeline_summary filtered",
            r_summary_filtered["status"] == "ok"
            and r_summary_filtered["data"]["total_deals"] == 2  # Acme Healthcare (Bob) + Apex Retail (Bob)
            and r_summary_filtered["data"]["total_value"] == 330000.0,  # 150k + 180k
            f"deals={r_summary_filtered['data']['total_deals']} value={r_summary_filtered['data']['total_value']}"
        )

    # Empty CRM scenario via a temp directory
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        (data_dir / "accounts.json").write_text(json.dumps({"accounts": []}))
        (data_dir / "opportunities.json").write_text(json.dumps({"opportunities": []}))
        os.environ["SALESFLOW_DATA_DIR"] = tmp
        try:
            async with Client(mcp) as c:
                r_empty = await call(c, "get_pipeline_summary", {})
                record(
                    "empty CRM handled safely",
                    r_empty["status"] == "ok"
                    and r_empty["data"]["total_deals"] == 0
                    and r_empty["data"]["total_value"] == 0.0,
                    f"deals={r_empty['data']['total_deals']} value={r_empty['data']['total_value']}"
                )
        finally:
            del os.environ["SALESFLOW_DATA_DIR"]

    # Print results
    width = max(len(n) for n, _, _ in results)
    for n, s, d in results:
        print(f"{s:<28} {n:<{width}}  {d}")
    failed = [n for n, s, _ in results if s == "FAIL"]
    print(f"\n{len(results)} checks, {len(failed)} failed" + (": " + ", ".join(failed) if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
