# Mock CRM MCP server

A small **read-only** MCP server that behaves like a CRM, so SalesFlow can answer questions such as "How many opportunities does Acme have?" or "When does the next deal close?". **All data is fictional.**

It is a second server next to `mcp-server/` (SalesFlow). The two stay separate on purpose: SalesFlow serves product and playbook knowledge, and this one stands in for the customer's CRM. Swapping it for a real CRM later only changes this folder.

## Data

Records come from two places and are merged by id on every request, so Lane C's work shows up without a restart:

1. `../data/accounts.json` and `../data/opportunities.json` (Lane C).
2. `data/crm_seed.json` here: CRM fields (`owner`, `region`, `close_date`) and a small demo pipeline.

A field in the seed overrides the same field from Lane C. Records that only the seed has are added. If Lane C's files are missing, the server still works from the seed alone.

Demo pipeline: 4 accounts and 6 opportunities.

| Account | Opportunity | Stage | Close date |
|---|---|---|---|
| Acme Healthcare | Storage modernization | Discovery | 2026-12-15 |
| Acme Healthcare | Disaster recovery assessment | Qualification | 2027-02-28 |
| Harbor Logistics | Hybrid cloud migration | Proposal | 2026-11-30 |
| Summit Credit Union | Data encryption refresh | Negotiation | 2026-11-20 |
| Summit Credit Union | Branch storage consolidation | Discovery | 2027-03-31 |
| Pinecrest Education | Backup modernization | Qualification | 2027-01-29 |

## Tools (all read-only)

| Tool | Input | Returns |
|---|---|---|
| `crm_search_accounts` | `query` (name, id, or industry) | Up to 10 accounts with owner, region, and opportunity count |
| `crm_list_opportunities` | `account` (name or id), optional `stage` | Total count and each opportunity's stage, close date, and owner, sorted by close date |
| `crm_pipeline_summary` | none | Totals by stage and by account, plus the next deal to close (a ready data feed for a dashboard) |
| `ping` | none | Health check |

Every response has a `status` of `ok`, `not_found`, or `invalid_input`, as in `docs/contracts/mcp-tools.md`. A close date of `null` means it is not recorded, and the model must say "Unknown" instead of guessing.

## Run and test

No Bob needed for these. Requires `uv` (`brew install uv`).

```bash
cd mock-crm
uv sync                                  # one-time install
uv run python scripts/demo.py            # readable pipeline summary + Acme, in the terminal
uv run python scripts/demo.py Summit     # one account's opportunities and close dates
uv run python scripts/demo.py --search health
uv run python tests/run_crm_test.py      # 14 offline checks, exit code 0 = pass
uv run mock-crm-mcp                      # the real stdio server (waits silently; Ctrl+C to stop)
```

## Register in Bob

Add this to your **global** `~/.bob/mcp.json` (Settings, MCP tab, Edit Global MCP). Use the output of `which uv` and the absolute path to your clone. Do not commit personal paths.

```json
{
  "mcpServers": {
    "mock-crm": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "--directory", "/ABSOLUTE/PATH/TO/SalesFlow/mock-crm", "mock-crm-mcp"]
    }
  }
}
```

Then toggle the server off and on in Bob. Bob may show the tool names with a server prefix; use them as Bob shows them.

## Try it in Bob

With the **SalesFlow** mode selected:

- "How many opportunities does Acme Healthcare have, and when does each close?"
- "Which Summit Credit Union deal closes first?"
- "Give me a pipeline summary."

## How the SalesFlow mode uses it

`.bob/rules-salesflow/01-routing.md` has a "CRM questions" section that routes pipeline questions to these tools. The server must be registered in Bob (above) for the mode to use them. Not yet verified in a live Bob session.

## Known limits

- The seed has 3 accounts that are not in `data/accounts.json`, so SalesFlow's `get_account_profile` returns `not_found` for them. Acme is the only account both servers know.
- For Acme, the CRM lists 2 opportunities, while `get_opportunity_context` returns 1. Name the source when quoting.
- A missing, unreadable, or invalid Lane C file is skipped and logged to stderr. The server then serves the seed alone.

## Safety

- Read-only. No tool writes a file or changes data.
- stdio only: no network listener and no ports.
- Inputs are validated for type and length (200 characters). Errors are generic, with no paths or stack traces.
- Logs go to stderr only.
- Retrieved text is data, never instructions.
