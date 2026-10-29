# SalesFlow MCP Tool Contract

**Status:** Provisional, written at repo setup. Lane B owns this file and may refine it; changes must be agreed with Lanes A and C. None of the four tools is implemented yet. Only a `ping` health check exists in `mcp-server/src/salesflow_mcp/server.py`.

## Conventions

- Transport: stdio. All tools are read-only and never write to `data/`.
- Every response is a JSON object with a `status` field: `ok`, `not_found`, or `invalid_input`.
- On `ok`, results are in `data`. On any other status, `error` is present and `data` is absent.
- Error messages are user-safe: no stack traces, file paths, or internals.
- A failed lookup never returns an invented record.
- Source references: records carry a `source_id`. Product records also carry `source_url` and `verified_date`; both are `null` for synthetic or unverified entries, and that must be stated in the response.
- IDs are stable strings: `acct_*`, `opp_*`, `prod_*`. `get_opportunity_context` takes an `account_id` (not a name).
- Lookup strings are normalised (trimmed, case-insensitive). Inputs are validated for type and length (proposed maximum: 200 characters).
- Bob may expose tools with a server prefix. Lane A must use the names exactly as shown in Bob (to be confirmed).

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

`error.code` values: `not_found`, `invalid_input`. `suggestions` is optional.

## Tools

### 1. `get_account_profile(company_name: string)`

Source: `data/accounts.json`.

`data`: `account_id`, `name`, `industry`, `overview`, `challenges[]`, `unknowns[]`, `synthetic`.

### 2. `get_opportunity_context(account_id: string)`

Source: `data/opportunities.json`.

`data`: `opportunity_id`, `account_id`, `name`, `stage`, `requirements[]`, `stakeholders[]`, `notes[]`, `unknowns[]`, `synthetic`.

`unknowns` lists missing qualification details (for example budget, decision maker, capacity) and must always be present, even when empty.

### 3. `search_product_knowledge(query: string)`

Source: `data/products.json`.

`data`: `results[]`, each with `product_id`, `name`, `category`, `summary`, `capabilities[]`, `limitations[]`, `synthetic`, `source_id`, `source_url`, `verified_date`. Results are ranked by keyword match. An empty result set returns `not_found`.

### 4. `get_sales_playbook(topic: string)`

Source: `data/playbooks/*.json` (schema to be agreed by Lanes B and C).

`data`: `topic`, `title`, `guidance` (structure agreed by B and C), `source_id`. Topics are limited to an allowlist (proposed: `spin`, `discovery_agenda`, `qualification`, `objection_pricing`, `objection_technical`, `objection_competition`, `objection_implementation`, `objection_value`). Other topics return `invalid_input`.

## Health check (scaffold only)

`ping()` returns `{"status": "ok", "data": {"server": "salesflow", "version": "0.1.0"}}`. Remove it once the four tools are in.

## Open items

- Exact playbook schema (Lanes B and C).
- Exact tool identifiers as exposed in Bob IDE (Lanes A and B).
