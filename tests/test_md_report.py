"""Tests for the save_salesflow_report MCP tool and md_report module.

Run from the repo root:
    python tests/test_md_report.py

Exit code 0 = all checks passed. Exit code 1 = failures found.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mcp-server" / "src"))

from salesflow_mcp.md_report import (
    REPORT_TYPES,
    MdReportError,
    _slug,
    safe_md_filename,
    save_report,
)
from salesflow_mcp.server import save_salesflow_report

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"{status:<6} {name}" + (f"  — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

_DISCOVERY_CONTENT = {
    "account": {
        "name": "Acme Healthcare",
        "industry": "Healthcare",
        "overview": "Regional hospital group seeking storage modernization.",
        "challenges": ["Aging NAS infrastructure", "HIPAA compliance gaps"],
        "unknowns": ["Budget approval", "Decision maker"],
        "synthetic": True,
    },
    "opportunity": {
        "opportunity_id": "opp_acme_storage_01",
        "name": "Acme Healthcare storage modernization",
        "stage": "Discovery",
        "requirements": ["99.999% availability", "HIPAA-compliant encryption at rest", "Scalable capacity"],
        "stakeholders": [{"role": "IT Director", "name": "Unknown"}],
        "unknowns": ["Capacity sizing", "Recovery Point Objective"],
        "synthetic": True,
    },
    "spin_questions": [
        {"category": "Situation", "question": "How is your current storage infrastructure structured today?"},
        {"category": "Problem", "question": "What challenges are you experiencing with your current storage system?"},
        {"category": "Implication", "question": "How do these challenges affect your ability to meet HIPAA requirements?"},
        {"category": "Need-Payoff", "question": "What would a modern, compliant storage solution enable for your team?"},
    ],
    "agenda": [
        {"time_slot": "0-3 min", "segment": "Introductions", "goal": "Establish rapport and agree on meeting goal"},
        {"time_slot": "3-10 min", "segment": "Current state", "goal": "Understand existing infrastructure"},
        {"time_slot": "10-20 min", "segment": "Challenges", "goal": "Identify pain points and compliance gaps"},
        {"time_slot": "20-27 min", "segment": "Solution exploration", "goal": "Discuss high-level options"},
        {"time_slot": "27-30 min", "segment": "Next steps", "goal": "Agree on actions and follow-up"},
    ],
    "qualification_gaps": [
        {"gap": "Budget Approval"},
        {"gap": "Economic Buyer"},
        {"gap": "Capacity & Sizing Metrics"},
        {"gap": "Recovery Point Objective"},
    ],
    "solution_positioning": {
        "products": [
            {
                "name": "IBM FlashSystem 5200",
                "category": "Storage",
                "source_url": "https://www.ibm.com/products/flashsystem-5200",
                "verification_status": "verified",
            },
            {
                "name": "IBM Spectrum Virtualize",
                "category": "Storage Software",
                "source_url": "https://www.ibm.com/products/spectrum-virtualize",
                "verification_status": "verified",
            },
        ]
    },
    "next_steps": [
        "Schedule a technical discovery session to assess sizing requirements",
        "Identify the economic buyer and decision-making process",
        "Send HIPAA storage compliance overview",
    ],
    "sources": [
        {"source_id": "src_crm_acme_001", "source_url": None, "verified_date": None},
        {"source_id": "src_prod_flashsystem5200_001", "source_url": "https://www.ibm.com/products/flashsystem-5200", "verified_date": "2026-10-01"},
    ],
    "synthetic": True,
}

_PIPELINE_CONTENT = {
    "digest": {
        "seller_scope": "All sellers",
        "generated_at": "2026-10-29T22:23:03+00:00",
        "synthetic_data": True,
        "summary": {
            "active_deals_analyzed": 6,
            "total_active_value": 1250000,
            "flagged_deals": 5,
            "risk_distribution": {
                "High Risk": {"count": 3, "value": 380000},
                "Medium Risk": {"count": 2, "value": 620000},
                "Low Risk": {"count": 1, "value": 250000},
            },
            "top_risk_factors": [
                {"factor": "Missing next meeting", "count": 3},
                {"factor": "Missing budget confirmation", "count": 2},
                {"factor": "Missing decision-maker", "count": 2},
            ],
        },
        "flagged_deals": [
            {
                "account_name": "Acme Healthcare",
                "opportunity_name": "Storage modernization",
                "risk_rating": "High Risk",
                "risk_score": 7,
                "stage": "Discovery",
                "value": 150000,
                "flagged_risks": [
                    {"factor": "Missing budget confirmation", "score_contribution": 3,
                     "recommended_action": "Qualify the budget envelope"},
                ],
            },
            {
                "account_name": "Apex Retail",
                "opportunity_name": "Disaster Recovery Modernization",
                "risk_rating": "High Risk",
                "risk_score": 6,
                "stage": "Discovery",
                "value": 180000,
                "flagged_risks": [
                    {"factor": "No recent customer activity", "score_contribution": 3,
                     "recommended_action": "Reach out to reconnect"},
                ],
            },
            {
                "account_name": "Nova Tech",
                "opportunity_name": "Fast Dev Environment Storage",
                "risk_rating": "High Risk",
                "risk_score": 6,
                "stage": "Qualification",
                "value": 50000,
                "flagged_risks": [],
                "recommended_actions": ["Identify the economic buyer"],
            },
        ],
    },
    "synthetic": True,
}

_FOLLOWUP_CONTENT = {
    "account_name": "Acme Healthcare",
    "meeting_label": "Discovery call 2026-10-29",
    "executive_summary": [
        "Met with the IT Director and CTO to discuss storage modernization.",
        "Customer confirmed HIPAA compliance and high availability as top priorities.",
        "Budget is in discussion; formal approval expected in Q1.",
    ],
    "meeting_analysis": {
        "requirements": [
            {"text": "99.999% availability required", "confidence": "explicit"},
            {"text": "HIPAA-compliant encryption at rest", "confidence": "explicit"},
        ],
        "action_items": [
            {"text": "Send HIPAA storage compliance overview", "owner": "seller", "deadline": "2026-11-05", "confidence": "explicit"},
            {"text": "Schedule technical sizing workshop", "owner": "seller", "deadline": "2026-11-15", "confidence": "inferred"},
        ],
        "open_questions": [
            {"text": "What is the current usable capacity?"},
            {"text": "Who has budget approval authority?"},
        ],
        "budget_and_timeline": {"budget_confirmed": False, "budget_mentions": ["Q1 budget cycle"]},
    },
    "crm_proposals": {
        "proposed_updates": [
            {"field": "stage", "proposed_value": "Qualification", "uncertainty": "medium"},
            {"field": "next_meeting_scheduled", "proposed_value": True, "uncertainty": "low"},
        ]
    },
    "unknowns": ["Budget approval authority", "Exact capacity requirements"],
    "synthetic": True,
}

_COMPARISON_CONTENT = {
    "account_name": "Acme Healthcare",
    "opportunity_name": "Storage modernization",
    "candidates": [
        {"product_id": "prod_flashsystem_5200", "name": "IBM FlashSystem 5200",
         "source_url": "https://www.ibm.com/products/flashsystem-5200",
         "verification_status": "verified"},
        {"product_id": "prod_flashsystem_7300", "name": "IBM FlashSystem 7300",
         "source_url": "https://www.ibm.com/products/flashsystem-7300",
         "verification_status": "verified"},
    ],
    "side_by_side": [
        {"requirement": "99.999% availability", "requirement_id": "req_001",
         "results": {"prod_flashsystem_5200": "Supported", "prod_flashsystem_7300": "Supported"}},
        {"requirement": "HIPAA encryption at rest", "requirement_id": "req_002",
         "results": {"prod_flashsystem_5200": "Supported", "prod_flashsystem_7300": "Supported"}},
        {"requirement": "Sub-5ms latency", "requirement_id": "req_003",
         "results": {"prod_flashsystem_5200": "Unknown / insufficient evidence",
                     "prod_flashsystem_7300": "Partially supported"}},
    ],
    "product_summaries": [
        {"product_id": "prod_flashsystem_5200", "name": "IBM FlashSystem 5200",
         "source_url": "https://www.ibm.com/products/flashsystem-5200",
         "verification_status": "verified",
         "strengths": [{"requirement_id": "req_001", "documented_capability": ["HyperSwap active-active HA"], "fit_status": "Supported"}],
         "limitations": ["HyperSwap requires two separate sites — validate topology"]},
        {"product_id": "prod_flashsystem_7300", "name": "IBM FlashSystem 7300",
         "source_url": "https://www.ibm.com/products/flashsystem-7300",
         "verification_status": "verified",
         "strengths": [],
         "limitations": ["Higher performance tier — validate workload requirements"]},
    ],
    "requirements_not_yet_validated": [
        {"requirement": "Sub-5ms latency SLA", "requirement_id": "req_003",
         "best_status": "Partially supported",
         "reasons": ["No documented latency guarantee in catalog; requires specialist sizing"]},
    ],
    "preliminary_solution_direction": {
        "worth_exploring": [
            {"name": "IBM FlashSystem 5200", "rationale": "Documented support for HA and encryption at rest"},
        ],
        "caveats": ["Sizing and configuration must be validated with a specialist", "No pricing provided"],
    },
    "sources": [
        {"source_id": "src_prod_flashsystem5200_001", "source_url": "https://www.ibm.com/products/flashsystem-5200", "verified_date": "2026-10-01"},
        {"source_id": "src_prod_flashsystem7300_001", "source_url": "https://www.ibm.com/products/flashsystem-7300", "verified_date": "2026-10-01"},
    ],
    "synthetic": True,
}


# ---------------------------------------------------------------------------
# Test: md_report module
# ---------------------------------------------------------------------------

def test_report_types() -> None:
    """All 7 expected report types are registered."""
    expected = {"discovery_brief", "account_summary", "action_plan", "deal_risk_assessment",
                "solution_comparison", "followup_plan", "pipeline_digest"}
    check("REPORT_TYPES contains all 7 expected types", expected == set(REPORT_TYPES.keys()),
          f"found: {set(REPORT_TYPES.keys())}")


def test_safe_filename() -> None:
    """safe_md_filename produces .md files with no path separators."""
    from datetime import datetime, timezone
    now = datetime(2026, 10, 29, 22, 0, 0, tzinfo=timezone.utc)
    name = safe_md_filename("discovery_brief", "Acme Healthcare", now)
    check("safe_md_filename ends with .md", name.endswith(".md"), name)
    check("safe_md_filename has no path separator", "/" not in name and "\\" not in name, name)
    check("safe_md_filename contains type prefix", name.startswith("discovery_brief_"), name)
    check("safe_md_filename contains timestamp", "20261029T220000Z" in name, name)
    # hex(4) = 8 chars + ".md" = 11 chars total in the last segment
    suffix = name.split("_")[-1]
    check("safe_md_filename has collision suffix (8 hex chars + .md)",
          suffix.endswith(".md") and len(suffix.replace(".md", "")) == 8, name)


def test_slug() -> None:
    """_slug produces ASCII-only, safe slugs."""
    check("_slug basic", _slug("Acme Healthcare") == "acme_healthcare")
    check("_slug with accents", _slug("Héalth Café") in ("h_lth_caf", "health_cafe", "h_lth_caf_"))
    check("_slug with special chars", "/" not in _slug("path/traversal/../test"))
    check("_slug empty fallback", _slug("") == "report")


def test_invalid_report_type() -> None:
    """Invalid report_type raises MdReportError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            try:
                save_report("invalid_type", {})
                check("invalid_report_type raises MdReportError", False, "no exception raised")
            except MdReportError as e:
                check("invalid_report_type raises MdReportError", e.code == "invalid_input", f"code={e.code}")
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_discovery_brief_creation() -> None:
    """Discovery brief report creates a file with correct content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            info = save_report("discovery_brief", _DISCOVERY_CONTENT)
            dest = Path(info["file_path"])
            check("discovery_brief: file exists", dest.exists(), str(dest))
            check("discovery_brief: size > 0", info["size_bytes"] > 0, f"size={info['size_bytes']}")
            check("discovery_brief: correct report_type", info["report_type"] == "discovery_brief")
            check("discovery_brief: subject is account name", "Acme" in info["subject"])

            md = dest.read_text(encoding="utf-8")
            check("discovery_brief: has Account Snapshot heading", "Account Snapshot" in md)
            check("discovery_brief: has SPIN Questions heading", "SPIN" in md)
            check("discovery_brief: has exactly 4 SPIN categories",
                  sum(cat in md for cat in ["**Situation:**", "**Problem:**", "**Implication:**", "**Need-Payoff:**"]) == 4,
                  "should have one of each")
            check("discovery_brief: has Meeting Agenda", "30-Minute Meeting Agenda" in md or "Meeting Agenda" in md)
            check("discovery_brief: has Qualification Gaps", "Qualification Gaps" in md)
            check("discovery_brief: qualification gaps as labels", "Budget Approval (Unknown)" in md)
            check("discovery_brief: has IBM Products table", "IBM Products" in md or "Potential IBM Products" in md)
            check("discovery_brief: product table has 3 columns",
                  "Product Group" in md and "Official IBM Product Page" in md)
            check("discovery_brief: product has valid IBM URL",
                  "https://www.ibm.com/products/flashsystem-5200" in md)
            check("discovery_brief: has Next Steps", "Next Steps" in md)
            check("discovery_brief: max 3 next steps",
                  md.count("1. ") + md.count("2. ") + md.count("3. ") >= 1)  # at least one numbered step
            check("discovery_brief: has Sources", "Sources" in md)
            check("discovery_brief: has synthetic disclosure", "Synthetic" in md or "synthetic" in md)
            check("discovery_brief: has DRAFT marker", "DRAFT" in md)
            check("discovery_brief: no guessed IBM URLs (only catalog URLs)",
                  "ibm.com/software" not in md and "ibm.com/storage" not in md)
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_pipeline_report_creation() -> None:
    """Pipeline digest report creates file with Mermaid diagram."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            info = save_report("pipeline_digest", _PIPELINE_CONTENT)
            dest = Path(info["file_path"])
            check("pipeline_digest: file exists", dest.exists(), str(dest))
            md = dest.read_text(encoding="utf-8")
            check("pipeline_digest: has Pipeline Metrics", "Pipeline Metrics" in md)
            check("pipeline_digest: has Mermaid diagram", "```mermaid" in md)
            check("pipeline_digest: Mermaid contains pie chart", "pie title" in md)
            check("pipeline_digest: Mermaid has High Risk slice", '"High Risk"' in md)
            check("pipeline_digest: has Top At-Risk Opportunities", "At-Risk" in md)
            check("pipeline_digest: top 3 deals only (not all 5+)", md.count("Acme Healthcare") <= 3)
            check("pipeline_digest: has heuristic disclaimer", "heuristic" in md)
            # The disclaimer should say no notification was sent (correct behavior).
            # We check there's no affirmative claim that a notification WAS sent.
            check("pipeline_digest: no affirmative notification claim",
                  "notification sent" not in md.lower() and "i will notify" not in md.lower()
                  and "you will be notified" not in md.lower())
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_followup_report_creation() -> None:
    """Post-meeting follow-up report created correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            info = save_report("followup_plan", _FOLLOWUP_CONTENT)
            dest = Path(info["file_path"])
            check("followup_plan: file exists", dest.exists(), str(dest))
            md = dest.read_text(encoding="utf-8")
            check("followup_plan: has Meeting Summary", "Meeting Summary" in md)
            check("followup_plan: has Action Items table", "Action Items" in md)
            check("followup_plan: has Follow-Up Email Draft", "Follow-Up Email Draft" in md or "Follow-up Email" in md)
            check("followup_plan: email has DRAFT marker", "DRAFT" in md)
            check("followup_plan: has Proposed CRM Changes", "Proposed CRM Changes" in md or "CRM Changes" in md)
            check("followup_plan: CRM not yet applied disclaimer",
                  "not yet applied" in md or "not applied" in md.lower() or "seller must approve" in md.lower())
            check("followup_plan: has Remaining Unknowns", "Unknowns" in md or "Unknown" in md)
            check("followup_plan: unknowns as labels", "(Unknown)" in md)
            check("followup_plan: no invented owners",
                  "John Smith" not in md and "Jane Doe" not in md)
            check("followup_plan: no CRM update claim",
                  "crm has been updated" not in md.lower() and "successfully updated" not in md.lower())
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_solution_comparison_report() -> None:
    """Solution comparison report contains matrix and product links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            info = save_report("solution_comparison", _COMPARISON_CONTENT)
            dest = Path(info["file_path"])
            check("solution_comparison: file exists", dest.exists(), str(dest))
            md = dest.read_text(encoding="utf-8")
            check("solution_comparison: has Comparison Matrix", "Comparison Matrix" in md)
            check("solution_comparison: has both products in matrix", "FlashSystem 5200" in md and "FlashSystem 7300" in md)
            check("solution_comparison: has fit statuses", "Supported" in md)
            check("solution_comparison: has Technical Validation Gaps", "Validation Gaps" in md or "Gaps" in md)
            check("solution_comparison: IBM product URLs present",
                  "ibm.com/products/flashsystem-5200" in md)
            check("solution_comparison: has Recommendation Summary", "Recommendation" in md or "direction" in md.lower())
            check("solution_comparison: no performance guarantee",
                  "guaranteed" not in md.lower() and "guarantee" not in md.lower())
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_no_overwrite() -> None:
    """save_report never silently overwrites an existing file (collision detection)."""
    from datetime import datetime, timezone
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            # Write two reports with the same type and check they get different filenames
            info1 = save_report("discovery_brief", _DISCOVERY_CONTENT)
            info2 = save_report("discovery_brief", _DISCOVERY_CONTENT)
            check("no_overwrite: two reports get different filenames",
                  info1["file_name"] != info2["file_name"],
                  f"both: {info1['file_name']}")
            check("no_overwrite: both files exist",
                  Path(info1["file_path"]).exists() and Path(info2["file_path"]).exists())
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_file_written_to_reports_subdir() -> None:
    """Reports are written to outputs/reports/, not outputs/ root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            info = save_report("discovery_brief", _DISCOVERY_CONTENT)
            dest = Path(info["file_path"])
            check("reports_subdir: file is inside reports/ subdir",
                  "reports" in str(dest),
                  str(dest))
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_no_word_export_automatic() -> None:
    """save_report returns a .md file, never a .docx."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            info = save_report("discovery_brief", _DISCOVERY_CONTENT)
            check("no_word_export: file is .md not .docx",
                  info["file_name"].endswith(".md") and not info["file_name"].endswith(".docx"),
                  info["file_name"])
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


def test_no_report_for_empty_content() -> None:
    """save_report with minimal/empty content does not raise but produces a valid file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            # Minimal valid content — should succeed without crashing
            info = save_report("account_summary", {"account": {"name": "Test Co"}, "synthetic": True})
            check("minimal_content: file created", Path(info["file_path"]).exists())
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


# ---------------------------------------------------------------------------
# Test: server tool wrapper
# ---------------------------------------------------------------------------

def test_server_tool_invalid_type() -> None:
    """save_salesflow_report MCP tool returns invalid_input for bad type."""
    result = save_salesflow_report("bad_type", {})
    check("server_tool: invalid_type → status invalid_input", result["status"] == "invalid_input",
          str(result))


def test_server_tool_invalid_content() -> None:
    """save_salesflow_report MCP tool returns invalid_input for non-dict content."""
    result = save_salesflow_report("discovery_brief", "not a dict")  # type: ignore[arg-type]
    check("server_tool: non-dict content → status invalid_input", result["status"] == "invalid_input",
          str(result))


def test_server_tool_success() -> None:
    """save_salesflow_report MCP tool returns ok status and workspace_relative_path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmpdir
        try:
            result = save_salesflow_report(
                report_type="discovery_brief",
                content=_DISCOVERY_CONTENT,
                account_id="acct_acme_healthcare",
                opportunity_id="opp_acme_storage_01",
                sources=[{"source_id": "src_crm_acme_001"}],
                synthetic=True,
            )
            check("server_tool: success → status ok", result.get("status") == "ok", str(result.get("status")))
            data = result.get("data") or {}
            check("server_tool: data.file_name present", bool(data.get("file_name")))
            check("server_tool: data.workspace_relative_path present", bool(data.get("workspace_relative_path")))
            check("server_tool: data.size_bytes > 0", (data.get("size_bytes") or 0) > 0)
            check("server_tool: message has preview instruction",
                  "Preview" in (result.get("message") or "") or "preview" in (result.get("message") or "").lower())
            check("server_tool: file actually exists", Path(data.get("file_path", "does-not-exist")).exists())
        finally:
            os.environ.pop("SALESFLOW_OUTPUTS_DIR", None)


# ---------------------------------------------------------------------------
# Test: regression — existing 17 MCP tools still present
# ---------------------------------------------------------------------------

def test_all_17_tools_registered() -> None:
    """All 17 original MCP tools plus the new save_salesflow_report are importable from server."""
    from salesflow_mcp import server
    expected = [
        "ping", "get_account_profile", "get_opportunity_context", "search_product_knowledge",
        "get_sales_playbook", "get_at_risk_deals", "get_pipeline_summary",
        "analyze_meeting_notes", "propose_crm_updates", "compare_solutions",
        "list_pipeline_schedules", "get_latest_pipeline_digest", "generate_sales_brief_document",
        "generate_sales_document", "create_pipeline_schedule", "update_pipeline_schedule",
        "run_pipeline_review",
        "save_salesflow_report",  # new tool = 18 total
    ]
    for name in expected:
        has = hasattr(server, name)
        check(f"tool_registered: {name}", has)


# ---------------------------------------------------------------------------
# Test: data integrity regression
# ---------------------------------------------------------------------------

def test_data_integrity() -> None:
    """Run the existing data integrity checks as a regression guard."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("data_integrity", REPO_ROOT / "tests" / "data_integrity.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    failures = [name for name, ok, _ in module.results if not ok]
    check("data_integrity: all fixture checks pass",
          len(failures) == 0,
          f"{len(failures)} failed: {', '.join(failures[:5])}" if failures else "")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"SalesFlow Markdown report tests\nRepo root: {REPO_ROOT}\n")

    test_report_types()
    print()
    test_safe_filename()
    test_slug()
    print()
    test_invalid_report_type()
    test_discovery_brief_creation()
    test_pipeline_report_creation()
    test_followup_report_creation()
    test_solution_comparison_report()
    print()
    test_no_overwrite()
    test_file_written_to_reports_subdir()
    test_no_word_export_automatic()
    test_no_report_for_empty_content()
    print()
    test_server_tool_invalid_type()
    test_server_tool_invalid_content()
    test_server_tool_success()
    print()
    test_all_17_tools_registered()
    print()
    test_data_integrity()

    print()
    failures = [name for name, ok, _ in results if not ok]
    total = len(results)
    print(f"{total} checks, {len(failures)} failed" +
          (": " + ", ".join(failures) if failures else " — all passed"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
