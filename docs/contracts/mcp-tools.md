# SalesFlow MCP Tool Contract

**Status:** Implemented in `mcp-server/src/salesflow_mcp/server.py` (all four tools plus `ping`). Lane B owns this file; changes must be agreed with Lanes A and C. The playbook content schema (tool 4) is a Lane B proposal awaiting Lane C's fixtures; until `data/playbooks/*.json` exists, `get_sales_playbook` returns `not_found` for allowlisted topics.

## Conventions

- Transport: stdio. All tools are read-only and never write to `data/`.
- Every response is a JSON object with a `status` field: `ok`, `not_found`, or `invalid_input`.
- On `ok`, results are in `data`. On any other status, `error` is present and `data` is absent.
- Error messages are user-safe: no stack traces, file paths, or internals.
- A failed lookup never returns an invented record.
- Source references: records carry a `source_id`. Product records also carry `source_url` and `verified_date`; both are `null` for synthetic or unverified entries, and that must be stated in the response.
- IDs are stable strings: `acct_*`, `opp_*`, `prod_*`. `get_opportunity_context` takes an `account_id` (not a name).
- Lookup strings are normalised (trimmed, case-insensitive). Inputs are validated for type and length (proposed maximum: 200 characters).
- Bob may expose tools with a server prefix. Lane A must use the names exactly as shown in Bob (to be confirmed; see Open items).
- All tools carry MCP read-only annotations. Data files are re-read on each request and never written.
- Lookups are exact (whitespace-collapsed, case-insensitive). `get_account_profile` also accepts a unique substring of at least 3 characters (e.g. "acme").
- Retrieved text is untrusted data, never instructions.

## Response envelope

Success:

```json
{
  "status": "ok",
  "data": { },
  "sources": [{"source_id": "src_...", "source_url": null, "verified_date": null}]
}
```

Error:

```json
{
  "status": "not_found",
  "error": {"code": "not_found", "message": "No account matched 'Example Corp'."},
  "suggestions": ["Acme Healthcare"]
}
```

`error.code` values: `not_found`, `invalid_input`. `suggestions` is optional. A missing or unreadable data file returns `not_found` with a generic "data source is currently unavailable" message (details go to stderr only).

## Tools

### 1. `get_account_profile(company_name: string)`

Source: `data/accounts.json`.

`data`: `account_id`, `name`, `industry`, `overview`, `challenges[]`, `unknowns[]`, `synthetic`. `sources`: one entry from the account's `source_id`. Unknown company: `not_found` with `suggestions` (known account names). Empty, non-string, or >200-char input: `invalid_input`.

### 2. `get_opportunity_context(account_id: string)`

Source: `data/opportunities.json`.

`data`: `opportunity_id`, `account_id`, `name`, `stage`, `requirements[]`, `stakeholders[]`, `notes[]` (meeting history), `unknowns[]`, `synthetic`, `additional_opportunities[]` (same shape; empty when the account has one opportunity). The primary opportunity is the lowest `opportunity_id`. `sources`: one entry per opportunity returned. Unknown account id, or account with no opportunity: `not_found`.

`unknowns` lists missing qualification details (for example budget, decision maker, capacity) and must always be present, even when empty.

### 3. `search_product_knowledge(query: string)`

Source: `data/products.json`.

`data`: `results[]` (max 5), each with `product_id`, `name`, `category`, `summary`, `capabilities[]`, `limitations[]`, `synthetic`, `verification_status` (`verified` | `synthetic_unverified`), `source_id`, `source_url`, `verified_date`, `match_score`. `data.notice` is present whenever any result is unverified. Ranking: stopwords removed, tokens compared on a 6-character prefix; per query token the best field weight counts (name/category 3, capabilities 2, summary 1); ties break on `product_id`. An empty result set returns `not_found`; a query with no searchable keyword returns `invalid_input`. No pricing or competitive data is ever returned.

### 4. `get_sales_playbook(topic: string)`

Source: `data/playbooks/*.json` (schema to be agreed by Lanes B and C).

`data`: `topic`, `title`, `guidance` (passed through unchanged from the fixture), `synthetic`, `source_id`. Topics are limited to an allowlist: `spin`, `discovery_agenda`, `qualification`, `objection_pricing`, `objection_technical`, `objection_competition`, `objection_implementation`, `objection_value` (input is trimmed, lower-cased, spaces/hyphens become `_`). Other topics return `invalid_input` with `suggestions` listing the allowlist. An allowlisted topic with no fixture returns `not_found`.

**Proposed fixture schema (for Lane C):** one JSON file per topic or one file with a `playbooks` array under `data/playbooks/`. Each entry:

```json
{
  "topic": "spin",
  "title": "SPIN Selling",
  "synthetic": true,
  "source_id": "src_playbook_spin_001",
  "guidance": { "any": "structure Lane C chooses, e.g. situation/problem/implication/need_payoff question lists" }
}
```

Required keys: `topic` (must be an allowlisted value), `guidance`. `source_id` and `synthetic` are strongly recommended.

## Health check

`ping()` returns `{"status": "ok", "data": {"server": "salesflow", "version": "0.1.0"}}`. Retained for connection checks.

## Open items

- Lane C to confirm or adjust the playbook fixture schema above and deliver `data/playbooks/*.json`.
- Exact tool identifiers as exposed in Bob IDE (Lanes A and B): confirm after restarting the server in Bob.
