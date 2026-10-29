"""Lane B tool tests, run through the FastMCP in-memory test client.

Run (from mcp-server/):  uv run python tests/run_tools_test.py

Real-data tests use the repo's data/ fixtures. Playbook tests that need content
use a TEMPORARY synthetic fixture in a temp dir because Lane C has not delivered
data/playbooks/*.json yet. Those are labelled "CODE PATH OK (temp fixture)", not
real-data success.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from fastmcp import Client

from salesflow_mcp.server import mcp

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "", label: str = "PASS") -> None:
    results.append((name, label if ok else "FAIL", detail))


async def call(client: Client, tool: str, args: dict) -> dict:
    res = await client.call_tool(tool, args, raise_on_error=False)
    return res.structured_content if res.structured_content is not None else json.loads(res.content[0].text)


def is_error(r: dict, status: str) -> bool:
    return (
        r.get("status") == status
        and "data" not in r
        and r.get("error", {}).get("code") == status
        and bool(r["error"].get("message"))
    )


async def main() -> None:
    async with Client(mcp) as c:
        tools = sorted(t.name for t in await c.list_tools())
        expected = sorted(["ping", "get_account_profile", "get_opportunity_context", "search_product_knowledge", "get_sales_playbook"])
        record("tool list", tools == expected, str(tools))

        r = await call(c, "ping", {})
        record("ping", r == {"status": "ok", "data": {"server": "salesflow", "version": "0.1.0"}}, json.dumps(r))

        # 1. valid account (mixed case / extra whitespace)
        r = await call(c, "get_account_profile", {"company_name": "  aCmE   healthcare "})
        d = r.get("data", {})
        record(
            "1 account Acme (case-insens.)",
            r["status"] == "ok" and d.get("account_id") == "acct_acme_healthcare" and d.get("industry") == "Healthcare"
            and bool(d.get("challenges")) and r["sources"][0]["source_id"] == "src_crm_acme_001",
            json.dumps(r)[:110],
        )
        # 2. unknown company / invalid
        r = await call(c, "get_account_profile", {"company_name": "Example Corp"})
        record("2 unknown company", is_error(r, "not_found"), json.dumps(r)[:110])
        r = await call(c, "get_account_profile", {"company_name": "   "})
        record("2b empty company", is_error(r, "invalid_input"), r["error"]["message"])
        r = await call(c, "get_account_profile", {"company_name": "x" * 201})
        record("2c overlong company", is_error(r, "invalid_input"), r["error"]["message"])

        # 3. opportunity
        r = await call(c, "get_opportunity_context", {"account_id": "acct_acme_healthcare"})
        d = r.get("data", {})
        record(
            "3 opportunity Acme",
            r["status"] == "ok" and d.get("opportunity_id") == "opp_acme_storage_01" and d.get("stage") == "Discovery"
            and d.get("unknowns") == ["budget", "decision maker", "usable capacity"] and bool(d.get("notes"))
            and r["sources"][0]["source_id"] == "src_crm_opp_acme_001",
            json.dumps(r)[:110],
        )
        # 4. missing / empty account id
        r = await call(c, "get_opportunity_context", {"account_id": "acct_nope"})
        record("4 missing account id", is_error(r, "not_found"), r["error"]["message"])
        r = await call(c, "get_opportunity_context", {"account_id": ""})
        record("4b empty account id", is_error(r, "invalid_input"), r["error"]["message"])

        # 5. product search
        for q in ("high availability", "storage", "disaster recovery"):
            r = await call(c, "search_product_knowledge", {"query": q})
            res = r.get("data", {}).get("results", [])
            ok = (
                r["status"] == "ok" and bool(res) and res[0]["product_id"] == "prod_storage_01"
                and res[0]["verification_status"] == "synthetic_unverified" and res[0]["source_url"] is None
                and "notice" in r["data"]
            )
            record(f"5 product search '{q}'", ok, f"top={res[0]['product_id'] if res else None} score={res[0]['match_score'] if res else None}")
        r = await call(c, "search_product_knowledge", {"query": "quantum blockchain"})
        record("5b product no match", is_error(r, "not_found"), r["error"]["message"])
        # 6. invalid / empty query
        for q in ("", "   ", "the and of"):
            r = await call(c, "search_product_knowledge", {"query": q})
            record(f"6 invalid query {q!r}", is_error(r, "invalid_input"), r["error"]["message"])

        # 7/8 playbook against REAL data
        r = await call(c, "get_sales_playbook", {"topic": "spin"})
        if r["status"] == "ok":
            record("7 SPIN playbook (real data)", True, f"title={r['data']['title']}")
        else:
            record(
                "7 SPIN playbook (real data)", is_error(r, "not_found"),
                "BLOCKED on Lane C: data/playbooks/ has no content. " + r["error"]["message"], label="BLOCKED",
            )
        r = await call(c, "get_sales_playbook", {"topic": "pirate_talk"})
        record("8 unsupported playbook topic", is_error(r, "invalid_input") and "suggestions" in r, r["error"]["message"])
        r = await call(c, "get_sales_playbook", {"topic": ""})
        record("8b empty playbook topic", is_error(r, "invalid_input"), r["error"]["message"])

    # Playbook code path with a TEMP fixture (not real data) + data-unavailable handling
    with tempfile.TemporaryDirectory() as tmp:
        pb = Path(tmp) / "playbooks"
        pb.mkdir()
        (pb / "spin.json").write_text(json.dumps({
            "topic": "spin", "title": "SPIN (temp test fixture)", "synthetic": True,
            "source_id": "src_test_tmp", "guidance": {"situation": ["q1"]},
        }))
        os.environ["SALESFLOW_DATA_DIR"] = tmp
        try:
            async with Client(mcp) as c:
                r = await call(c, "get_sales_playbook", {"topic": " SPIN "})
                record(
                    "7' SPIN code path",
                    r["status"] == "ok" and r["data"]["guidance"] == {"situation": ["q1"]} and r["sources"][0]["source_id"] == "src_test_tmp",
                    "temp fixture", label="CODE PATH OK (temp fixture)",
                )
                r = await call(c, "get_sales_playbook", {"topic": "qualification"})
                record("7'' allowlisted topic w/o content", is_error(r, "not_found"), r["error"]["message"])
                r = await call(c, "get_account_profile", {"company_name": "Acme Healthcare"})
                record("data-unavailable handled safely", is_error(r, "not_found") and "/" not in r["error"]["message"], r["error"]["message"])
        finally:
            del os.environ["SALESFLOW_DATA_DIR"]

    width = max(len(n) for n, _, _ in results)
    for n, s, d in results:
        print(f"{s:<28} {n:<{width}}  {d[:110]}")
    failed = [n for n, s, _ in results if s == "FAIL"]
    print(f"\n{len(results)} checks, {len(failed)} failed" + (": " + ", ".join(failed) if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
