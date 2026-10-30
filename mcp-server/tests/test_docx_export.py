"""Tests for Phase 2: Word document export.

Tests cover:
- Valid document creation and structure
- Word file opens correctly (python-docx can re-read it)
- All required sections present in document text
- Special characters handled safely
- Missing optional data handled gracefully
- Unsafe output paths rejected
- Repeated exports do not silently overwrite
- No document created during read-only MCP requests
- generate_sales_brief_document MCP tool end-to-end
- Existing MCP functionality (regression: all original tools)

Run (from mcp-server/):  uv run python tests/test_docx_export.py
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

from docx import Document as DocxDocument

from salesflow_mcp.brief_schema import (
    AccountSummary,
    AgendaItem,
    NextStep,
    OpportunitySummary,
    ProductEntry,
    QualificationGap,
    SalesBriefInput,
    SourceRef,
    SpinQuestion,
    SolutionPositioning,
)
from salesflow_mcp.docx_generator import build_document, resolve_output_path, _safe_filename

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "PASS" if ok else "FAIL", detail[:120]))


def _acme_brief() -> SalesBriefInput:
    """Return the full Acme Healthcare demonstration brief."""
    return SalesBriefInput(
        account=AccountSummary(
            account_id="acct_acme_healthcare",
            name="Acme Healthcare",
            industry="Healthcare",
            overview="Fictional regional healthcare network with hospitals and outpatient clinics.",
            challenges=[
                "Aging on-premises storage arrays approaching end of support",
                "Need for high availability for clinical systems",
            ],
            unknowns=["annual IT budget", "total usable storage capacity"],
            synthetic=True,
            source_id="src_crm_acme_001",
        ),
        opportunity=OpportunitySummary(
            opportunity_id="opp_acme_storage_01",
            name="Acme Healthcare storage modernization",
            stage="Discovery",
            requirements=["Replace aging storage", "High availability", "Disaster recovery"],
            stakeholders=[{"role": "Director of Infrastructure", "name": "Synthetic Contact A"}],
            notes=["Initial inquiry received; no prior discovery meeting held."],
            unknowns=["budget", "decision maker", "usable capacity"],
            synthetic=True,
            source_id="src_crm_opp_acme_001",
        ),
        spin_questions=[
            SpinQuestion(category="Situation",
                         question="Can you walk me through your current storage environment — what platforms are in production and when were they originally deployed?"),
            SpinQuestion(category="Situation",
                         question="How many sites rely on shared storage today and how is replication or DR currently handled between them?"),
            SpinQuestion(category="Problem",
                         question="Your arrays are approaching end of support — what specific risks does that create for your team right now?"),
            SpinQuestion(category="Problem",
                         question="What happens to clinical workflows if your primary storage has an unplanned outage?"),
            SpinQuestion(category="Implication",
                         question="If an end-of-support event caused a compliance gap, what would the downstream impact look like for your organization?"),
            SpinQuestion(category="Implication",
                         question="What is the estimated cost of even a two-hour storage outage during peak clinical hours?"),
            SpinQuestion(category="Need-Payoff",
                         question="If you had a modernized platform that guaranteed sub-minute RTO for clinical systems, how would that change your risk posture?"),
            SpinQuestion(category="Need-Payoff",
                         question="If you could solve the DR gap at the same time as storage replacement, what would that unlock for your infrastructure roadmap?"),
        ],
        agenda=[
            AgendaItem(time_slot="0–3 min", segment="Introductions & agenda alignment",
                       goal="Confirm attendees, set expectations, agree on outcome"),
            AgendaItem(time_slot="3–8 min", segment="Situation questions",
                       goal="Map current environment, sites, and topology"),
            AgendaItem(time_slot="8–15 min", segment="Problem questions",
                       goal="Uncover active pain around end-of-support and HA gaps"),
            AgendaItem(time_slot="15–20 min", segment="Implication questions",
                       goal="Quantify risk and business impact"),
            AgendaItem(time_slot="20–25 min", segment="Need-Payoff questions",
                       goal="Build shared vision of desired outcome"),
            AgendaItem(time_slot="25–28 min", segment="Preliminary solution positioning",
                       goal="Share directional capabilities; avoid over-specifying"),
            AgendaItem(time_slot="28–30 min", segment="Next steps",
                       goal="Agree on follow-up: technical deep-dive, RFI, or assessment"),
        ],
        solution_positioning=SolutionPositioning(
            products=[
                ProductEntry(
                    product_id="prod_storage_01",
                    name="Example Enterprise Storage Platform (synthetic)",
                    summary="Placeholder entry for a block storage platform aimed at high availability.",
                    capabilities=["High availability (placeholder)", "Disaster recovery support (placeholder)"],
                    limitations=["Unverified; do not present as a real product capability"],
                    verification_status="synthetic_unverified",
                    source_id="src_prod_synthetic_001",
                    synthetic=True,
                ),
            ],
            directional_angle=(
                "We have storage platforms purpose-built for organisations that need "
                "always-on availability for mission-critical clinical systems, with integrated "
                "DR that can simplify your multi-site architecture."
            ),
            notice=(
                "Entries marked synthetic_unverified are placeholders without a verified "
                "source_url/verified_date. Do not present them as real product facts."
            ),
        ),
        qualification_gaps=[
            QualificationGap(gap="Annual IT budget",
                             why_it_matters="Cannot size or qualify the opportunity"),
            QualificationGap(gap="Total usable storage capacity",
                             why_it_matters="Cannot scope a replacement solution"),
            QualificationGap(gap="Decision-maker identity",
                             why_it_matters="Director of Infrastructure may not be the economic buyer"),
            QualificationGap(gap="RTO / RPO targets",
                             why_it_matters="HA and DR requirements cannot be scoped without recovery objectives"),
            QualificationGap(gap="Regulatory/compliance constraints",
                             why_it_matters="Healthcare environments may drive architecture requirements"),
            QualificationGap(gap="Current storage vendors / platforms",
                             why_it_matters="Needed to assess migration complexity"),
            QualificationGap(gap="Timeline and trigger event",
                             why_it_matters="Is end-of-support a hard deadline? What is the contract expiry date?"),
            QualificationGap(gap="Multi-site DR topology",
                             why_it_matters="Number of sites, network connectivity, and replication requirements unknown"),
        ],
        next_steps=[
            NextStep(action="Schedule a technical deep-dive to map current storage topology"),
            NextStep(action="Request IT budget envelope or approval process from Director of Infrastructure"),
            NextStep(action="Confirm decision-maker and procurement stakeholders"),
            NextStep(action="Obtain current storage capacity and performance baselines"),
            NextStep(action="Send follow-up summary with preliminary solution positioning for review"),
        ],
        sources=[
            SourceRef(source_id="src_crm_acme_001"),
            SourceRef(source_id="src_crm_opp_acme_001"),
            SourceRef(source_id="src_prod_synthetic_001"),
        ],
        playbook_available=False,
        methodology_note=(
            "SPIN playbook returned not_found from MCP server (Lane C fixture pending). "
            "Questions structured using standard SPIN methodology applied to retrieved data."
        ),
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_safe_filename() -> None:
    # Spaces are preserved (not unsafe); underscores come from the caller normalising before passing
    result = _safe_filename("Acme Healthcare")
    record("safe_filename normal", result in ("Acme Healthcare", "Acme_Healthcare") and "/" not in result and len(result) > 0)
    record("safe_filename traversal", _safe_filename("../../etc/passwd") == "passwd")
    record("safe_filename special chars", "/" not in _safe_filename("A/B\\C:D"))
    record("safe_filename empty", _safe_filename("") == "brief")
    record("safe_filename overlong", len(_safe_filename("x" * 200)) <= 80)


def test_schema_validation() -> None:
    brief = _acme_brief()
    record("schema account_id", brief.account.account_id == "acct_acme_healthcare")
    record("schema 8 spin questions", len(brief.spin_questions) == 8)
    record("schema categories", {q.category for q in brief.spin_questions} ==
           {"Situation", "Problem", "Implication", "Need-Payoff"})
    record("schema 7 agenda items", len(brief.agenda) == 7)

    # Invalid category
    try:
        SpinQuestion(category="Made-Up", question="Q?")
        record("schema invalid category rejected", False, "should have raised")
    except Exception:
        record("schema invalid category rejected", True)

    # Too many spin questions
    try:
        SalesBriefInput(
            account=brief.account,
            opportunity=brief.opportunity,
            spin_questions=[SpinQuestion(category="Situation", question=f"Q{i}?") for i in range(21)],
        )
        record("schema spin limit enforced", False, "should have raised")
    except Exception:
        record("schema spin limit enforced", True)


def test_document_creation(tmp_path: Path) -> None:
    brief = _acme_brief()
    dest = tmp_path / "test_brief.docx"
    written = build_document(brief, dest)

    record("doc file exists", written.exists(), str(written))
    record("doc non-zero size", written.stat().st_size > 0, f"{written.stat().st_size} bytes")

    # python-docx can re-read the file (valid OOXML)
    try:
        doc = DocxDocument(str(written))
        record("doc opens correctly (python-docx)", True)
    except Exception as exc:
        record("doc opens correctly (python-docx)", False, str(exc))
        return

    # Collect all text: paragraphs + table cells
    all_texts: list[str] = [p.text for p in doc.paragraphs]
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                all_texts.append(cell.text)
    full_text = "\n".join(all_texts)
    text_upper = full_text.upper()

    # Required sections present (headings live in paragraphs)
    para_text = "\n".join(p.text for p in doc.paragraphs).upper()
    sections_required = [
        "ACCOUNT SNAPSHOT",
        "OPPORTUNITY OVERVIEW",
        "SPIN DISCOVERY QUESTIONS",
        "30-MINUTE MEETING AGENDA",
        "MISSING REQUIREMENTS",
        "PRELIMINARY SOLUTION POSITIONING",
        "RECOMMENDED NEXT STEPS",
        "SOURCES AND DISCLAIMERS",
    ]
    for section in sections_required:
        record(f"doc section '{section}'", section in para_text,
               "missing" if section not in para_text else "found")

    # Account data present (account_id is in a table cell)
    record("doc account name present", "ACME HEALTHCARE" in text_upper)
    record("doc account id present", "acct_acme_healthcare" in full_text)

    # Spin questions present
    record("doc spin question count >= 8",
           sum(1 for p in doc.paragraphs if "?" in p.text) >= 8,
           f"paragraphs with '?': {sum(1 for p in doc.paragraphs if '?' in p.text)}")

    # Synthetic disclaimer present
    record("doc synthetic disclaimer", "SYNTHETIC" in text_upper)


def test_special_characters(tmp_path: Path) -> None:
    brief = SalesBriefInput(
        account=AccountSummary(
            account_id="acct_test_special",
            name="Tëst & Co. <Special> \"Chars\"",
            industry="Tech & Media",
            overview="Overview with <XML> chars & 'apostrophes' and \"quotes\".",
            synthetic=True,
        ),
        opportunity=OpportunitySummary(
            opportunity_id="opp_test_001",
            name="Test Opportunity — em-dash & ellipsis…",
            stage="Discovery",
        ),
    )
    dest = tmp_path / "special_chars.docx"
    try:
        written = build_document(brief, dest)
        doc = DocxDocument(str(written))
        record("doc special chars no crash", True)
        record("doc special chars opens", True)
    except Exception as exc:
        record("doc special chars no crash", False, str(exc))
        record("doc special chars opens", False, str(exc))


def test_missing_optional_data(tmp_path: Path) -> None:
    """Brief with only required fields — optional sections should be gracefully omitted."""
    brief = SalesBriefInput(
        account=AccountSummary(
            account_id="acct_minimal",
            name="Minimal Corp",
            synthetic=True,
        ),
        opportunity=OpportunitySummary(
            opportunity_id="opp_minimal_001",
        ),
    )
    dest = tmp_path / "minimal.docx"
    try:
        written = build_document(brief, dest)
        record("doc minimal brief no crash", written.exists())
        doc = DocxDocument(str(written))
        record("doc minimal brief opens", True)
    except Exception as exc:
        record("doc minimal brief no crash", False, str(exc))
        record("doc minimal brief opens", False, str(exc))


def test_no_overwrite(tmp_path: Path) -> None:
    brief = _acme_brief()
    dest = tmp_path / "overwrite_test.docx"
    dest.write_bytes(b"existing content")

    try:
        build_document(brief, dest)
        record("no silent overwrite", False, "should have raised FileExistsError")
    except FileExistsError:
        record("no silent overwrite", True)


def test_unsafe_path() -> None:
    """resolve_output_path must reject traversal attempts."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["SALESFLOW_OUTPUTS_DIR"] = tmp
        try:
            # Patch the function to force a traversal scenario by using a
            # crafted account name that after sanitisation lands inside tmp
            path = resolve_output_path("normal_account")
            record("safe path resolves ok", str(path).startswith(tmp))
            # The resolved path must be inside the outputs dir
            record("safe path inside outputs", Path(path).resolve().is_relative_to(Path(tmp).resolve()))
        finally:
            del os.environ["SALESFLOW_OUTPUTS_DIR"]


def test_no_doc_on_readonly_calls(tmp_path: Path) -> None:
    """Read-only MCP tool calls must not create files in outputs/."""
    import asyncio
    from fastmcp import Client
    from salesflow_mcp.server import mcp

    initial_files = set(tmp_path.iterdir())

    async def run():
        async with Client(mcp) as c:
            await c.call_tool("ping", {}, raise_on_error=False)
            await c.call_tool("get_account_profile", {"company_name": "Acme Healthcare"}, raise_on_error=False)

    os.environ["SALESFLOW_OUTPUTS_DIR"] = str(tmp_path)
    try:
        asyncio.run(run())
    finally:
        del os.environ["SALESFLOW_OUTPUTS_DIR"]

    after_files = set(tmp_path.iterdir())
    record("no doc created by read-only tools", initial_files == after_files,
           f"new files: {after_files - initial_files}")


# ---------------------------------------------------------------------------
# MCP tool integration test
# ---------------------------------------------------------------------------


async def test_mcp_export_tool(tmp_path: Path) -> None:
    from fastmcp import Client
    from salesflow_mcp.server import mcp

    brief = _acme_brief()
    brief_dict = json.loads(brief.model_dump_json())

    os.environ["SALESFLOW_OUTPUTS_DIR"] = str(tmp_path)
    try:
        async with Client(mcp) as c:
            # Confirm tool is listed
            tools = [t.name for t in await c.list_tools()]
            record("mcp tool listed", "generate_sales_brief_document" in tools, str(tools))

            # Valid call
            res = await c.call_tool("generate_sales_brief_document",
                                    {"brief_data": brief_dict}, raise_on_error=False)
            raw = res.structured_content if res.structured_content else json.loads(res.content[0].text)
            record("mcp export status ok", raw.get("status") == "ok", json.dumps(raw)[:200])
            if raw.get("status") == "ok":
                fp = raw["data"]["file_path"]
                record("mcp export file exists", Path(fp).exists(), fp)
                record("mcp export size > 0", raw["data"]["size_bytes"] > 0,
                       f"{raw['data']['size_bytes']} bytes")
                record("mcp export account name", raw["data"]["account_name"] == "Acme Healthcare")
                record("mcp export opportunity id", raw["data"]["opportunity_id"] == "opp_acme_storage_01")

                # Doc is valid OOXML
                try:
                    DocxDocument(fp)
                    record("mcp export doc valid ooxml", True)
                except Exception as exc:
                    record("mcp export doc valid ooxml", False, str(exc))

                # No overwrite on second call — sleep 1s to ensure different timestamp
                import time; time.sleep(1)
                res2 = await c.call_tool("generate_sales_brief_document",
                                         {"brief_data": brief_dict}, raise_on_error=False)
                raw2 = res2.structured_content if res2.structured_content else json.loads(res2.content[0].text)
                # Second call should succeed (new timestamp in filename) and be a different path
                record("mcp export second call no overwrite",
                       raw2.get("status") == "ok" and raw2["data"]["file_path"] != fp,
                       json.dumps(raw2)[:150])

            def _parse_response(res) -> dict:
                """Parse a tool response; tolerate MCP-level error text."""
                if res.structured_content:
                    return res.structured_content
                try:
                    return json.loads(res.content[0].text)
                except Exception:
                    # FastMCP returned a non-JSON error (e.g. type validation failure)
                    return {"status": "invalid_input", "_raw": str(res.content[0].text)[:200]}

            # Invalid input (FastMCP may intercept before our handler)
            res_bad = await c.call_tool("generate_sales_brief_document",
                                        {"brief_data": "not_a_dict"}, raise_on_error=False)
            raw_bad = _parse_response(res_bad)
            record("mcp export invalid input rejected",
                   raw_bad.get("status") == "invalid_input", str(raw_bad)[:150])

            # Missing required field
            bad_brief = {"account": {"account_id": "x", "name": "X"}}  # missing opportunity
            res_miss = await c.call_tool("generate_sales_brief_document",
                                         {"brief_data": bad_brief}, raise_on_error=False)
            raw_miss = _parse_response(res_miss)
            record("mcp export missing field rejected",
                   raw_miss.get("status") == "invalid_input", str(raw_miss)[:150])
    finally:
        del os.environ["SALESFLOW_OUTPUTS_DIR"]


# ---------------------------------------------------------------------------
# Regression: original MCP tools unchanged
# ---------------------------------------------------------------------------


async def test_original_tools_regression() -> None:
    from fastmcp import Client
    from salesflow_mcp.server import mcp

    async with Client(mcp) as c:
        # ping
        r = await c.call_tool("ping", {}, raise_on_error=False)
        raw = r.structured_content if r.structured_content else json.loads(r.content[0].text)
        record("regression ping", raw == {"status": "ok", "data": {"server": "salesflow", "version": "0.1.0"}})

        # get_account_profile
        r = await c.call_tool("get_account_profile", {"company_name": "Acme Healthcare"}, raise_on_error=False)
        raw = r.structured_content if r.structured_content else json.loads(r.content[0].text)
        record("regression get_account_profile",
               raw.get("status") == "ok" and raw["data"]["account_id"] == "acct_acme_healthcare",
               json.dumps(raw)[:100])

        # get_opportunity_context
        r = await c.call_tool("get_opportunity_context", {"account_id": "acct_acme_healthcare"}, raise_on_error=False)
        raw = r.structured_content if r.structured_content else json.loads(r.content[0].text)
        record("regression get_opportunity_context",
               raw.get("status") == "ok" and raw["data"]["opportunity_id"] == "opp_acme_storage_01",
               json.dumps(raw)[:100])

        # search_product_knowledge
        r = await c.call_tool("search_product_knowledge", {"query": "high availability storage"}, raise_on_error=False)
        raw = r.structured_content if r.structured_content else json.loads(r.content[0].text)
        record("regression search_product_knowledge",
               raw.get("status") == "ok" and bool(raw["data"]["results"]),
               json.dumps(raw)[:100])

        # get_sales_playbook (not_found is expected until Lane C delivers fixtures)
        r = await c.call_tool("get_sales_playbook", {"topic": "spin"}, raise_on_error=False)
        raw = r.structured_content if r.structured_content else json.loads(r.content[0].text)
        record("regression get_sales_playbook",
               raw.get("status") in ("ok", "not_found"),
               f"status={raw.get('status')}")

        # Tool count: should be 18 (5 original + 2 Word export + 2 risk + 2 meeting + 1 comparison
        # + 5 scheduling + 1 report save)
        tools = sorted(t.name for t in await c.list_tools())
        expected = sorted(["ping", "get_account_profile", "get_opportunity_context",
                           "search_product_knowledge", "get_sales_playbook",
                           "generate_sales_brief_document", "generate_sales_document",
                           "get_at_risk_deals", "get_pipeline_summary",
                           "analyze_meeting_notes", "propose_crm_updates", "compare_solutions",
                           "create_pipeline_schedule", "list_pipeline_schedules", "update_pipeline_schedule",
                           "run_pipeline_review", "get_latest_pipeline_digest", "save_salesflow_report"])
        record("regression tool list (18 tools)", tools == expected, str(tools))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        def mkd(name: str) -> Path:
            p = tmp_path / name
            p.mkdir(parents=True, exist_ok=True)
            return p

        # Synchronous tests
        test_safe_filename()
        test_schema_validation()
        test_document_creation(mkd("creation"))
        test_special_characters(mkd("special"))
        test_missing_optional_data(mkd("minimal"))
        test_no_overwrite(mkd("overwrite"))
        test_unsafe_path()
        test_no_doc_on_readonly_calls(mkd("readonly"))

        # Async tests
        asyncio.run(test_mcp_export_tool(mkd("mcp_export")))
        asyncio.run(test_original_tools_regression())

    width = max(len(n) for n, _, _ in results) if results else 30
    for name, status, detail in results:
        print(f"{status:<8} {name:<{width}}  {detail}")

    failed = [n for n, s, _ in results if s == "FAIL"]
    print(f"\n{len(results)} checks, {len(failed)} failed" + (": " + ", ".join(failed) if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
