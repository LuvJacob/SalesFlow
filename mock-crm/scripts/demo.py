"""Try the mock CRM from the terminal, without Bob.

Run (from mock-crm/):
    uv run python scripts/demo.py                  # pipeline summary + Acme
    uv run python scripts/demo.py "Summit"         # one account's opportunities
    uv run python scripts/demo.py --search health  # find accounts

Prints readable tables from the same functions the MCP tools use. ALL DATA IS FICTIONAL.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mock_crm import server  # noqa: E402

logging.getLogger("mock_crm").setLevel(logging.ERROR)


def table(rows: list[list[str]], header: list[str]) -> None:
    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    line = "  ".join(h.ljust(w) for h, w in zip(header, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


def show_pipeline() -> None:
    r = server.crm_pipeline_summary()["data"]
    print(f"\nPIPELINE (synthetic): {r['total_accounts']} accounts, {r['total_opportunities']} opportunities")
    table([[k, v] for k, v in r["by_stage"].items()], ["Stage", "Count"])
    n = r["next_to_close"]
    if n:
        print(f"\nNext to close: {n['name']} ({n['account_name']}), {n['stage']}, {n['close_date']}")


def show_account(name: str) -> None:
    r = server.crm_list_opportunities(name)
    if r["status"] != "ok":
        print(f"\n{r['error']['message']}  Try: {', '.join(r.get('suggestions', []))}")
        return
    d = r["data"]
    print(f"\n{d['account_name']}: {d['count']} opportunit{'y' if d['count'] == 1 else 'ies'}")
    table(
        [[o["name"], o["stage"], o["close_date"] or "Unknown", o["owner"] or "Unknown"] for o in d["opportunities"]],
        ["Opportunity", "Stage", "Close date", "Owner"],
    )


def show_search(query: str) -> None:
    r = server.crm_search_accounts(query)
    if r["status"] != "ok":
        print(f"\n{r['error']['message']}")
        return
    table(
        [[a["name"], a["industry"] or "", a["owner"] or "", a["opportunity_count"]] for a in r["data"]["accounts"]],
        ["Account", "Industry", "Owner", "Opps"],
    )


def main(argv: list[str]) -> None:
    if len(argv) >= 2 and argv[0] == "--search":
        show_search(" ".join(argv[1:]))
    elif argv:
        show_account(" ".join(argv))
    else:
        show_pipeline()
        show_account("Acme Healthcare")


if __name__ == "__main__":
    main(sys.argv[1:])
