"""Offline checks for the mock CRM MCP server (in-memory FastMCP client).

Run (from mock-crm/):  uv run python tests/run_crm_test.py
Exit code 0 means every check passed.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastmcp import Client  # noqa: E402

from mock_crm.server import mcp  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


async def call(client: Client, tool: str, args: dict | None = None) -> dict:
    result = await client.call_tool(tool, args or {}, raise_on_error=False)
    if result.is_error:
        return {"status": "tool_error"}
    return result.data if isinstance(result.data, dict) else json.loads(result.content[0].text)


async def main() -> None:
    async with Client(mcp) as c:
        tools = {t.name for t in await c.list_tools()}
        check("tools registered", tools == {"ping", "crm_search_accounts", "crm_list_opportunities", "crm_pipeline_summary"}, str(tools))

        r = await call(c, "ping")
        check("ping ok", r.get("status") == "ok")

        r = await call(c, "crm_list_opportunities", {"account": "Acme Healthcare"})
        d = r.get("data", {})
        check("acme has 2 opportunities", r.get("status") == "ok" and d.get("count") == 2, str(d.get("count")))
        check("acme sorted by close date", [o["close_date"] for o in d.get("opportunities", [])] == ["2026-12-15", "2027-02-28"])

        r = await call(c, "crm_list_opportunities", {"account": "acme"})
        check("partial name matches", r.get("status") == "ok" and r["data"]["account_id"] == "acct_acme_healthcare")

        r = await call(c, "crm_list_opportunities", {"account": "acct_summit_credit_union", "stage": "negotiation"})
        check("stage filter is case-insensitive", r.get("status") == "ok" and r["data"]["count"] == 1)

        r = await call(c, "crm_list_opportunities", {"account": "Zephyr Dynamics Corp"})
        check("unknown account is not_found, no invented record", r.get("status") == "not_found" and "data" not in r)

        r = await call(c, "crm_list_opportunities", {"account": "   "})
        check("blank input is invalid_input", r.get("status") == "invalid_input")

        r = await call(c, "crm_list_opportunities", {"account": "x" * 500})
        check("over-long input is invalid_input", r.get("status") == "invalid_input")

        r = await call(c, "crm_search_accounts", {"query": "healthcare"})
        check("search by industry", r.get("status") == "ok" and r["data"]["count"] >= 1)

        r = await call(c, "crm_search_accounts", {"query": "nothing-matches-this"})
        check("search miss is not_found", r.get("status") == "not_found")

        r = await call(c, "crm_pipeline_summary")
        d = r.get("data", {})
        check("pipeline totals", r.get("status") == "ok" and d.get("total_opportunities") == 6 and d.get("total_accounts") == 4, str(d))
        check("next to close is Summit encryption", (d.get("next_to_close") or {}).get("opportunity_id") == "opp_summit_security_01")

        r = await call(c, "crm_search_accounts", {"query": "acme"})
        check("response is flagged synthetic with a source", r["data"].get("synthetic") is True and r["sources"][0]["source_id"])

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) FAILED")
        sys.exit(1)
    print("\nAll checks passed")


if __name__ == "__main__":
    asyncio.run(main())
