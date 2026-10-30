# SalesFlow MCP Tool Contract

**Status:** Implemented in `mcp-server/src/salesflow_mcp/server.py` (core tools, risk, meeting-analysis, solution-comparison and scheduling tools, plus `ping`). Lane B owns this file; changes must be agreed with Lanes A and C. The playbook content schema (tool 4) is a Lane B proposal awaiting Lane C's fixtures; until `data/playbooks/*.json` exists, `get_sales_playbook` returns `not_found` for allowlisted topics.

## Conventions

- Transport: stdio. No tool writes to `data/`. All tools are read-only except the Word export and the scheduling tools (see "Scheduled pipeline briefings").
- Every response is a JSON object with a `status` field: `ok`, `not_found`, or `invalid_input`.
- On `ok`, results are in `data`. On any other status, `error` is present and `data` is absent.
- Error messages are user-safe: no stack traces, file paths, or internals.
- A failed lookup never returns an invented record.
- Source references: records carry a `source_id`. Product records also carry `source_url` and `verified_date`; both are `null` for synthetic or unverified entries, and that must be stated in the response.
- IDs are stable strings: `acct_*`, `opp_*`, `prod_*`. `get_opportunity_context` takes an `account_id` (not a name).
- Lookup strings are normalised (trimmed, case-insensitive). Inputs are validated for type and length (proposed maximum: 200 characters).
- Bob may expose tools with a server prefix. Lane A must use the names exactly as shown in Bob (to be confirmed; see Open items).
- Lookup tools carry MCP read-only annotations. Data files are re-read on each request and never written.
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

### 5. `compare_solutions(account_id?: string, requirements?: array, product_ids?: string[], focus_areas?: string[], max_candidates?: int)`

Source: `data/products.json` plus, when `account_id` is given, `data/accounts.json` and `data/opportunities.json` (primary opportunity). At least one of `account_id` or `requirements` is required. Implemented in `solution_comparison.py`; read-only.

- `requirements`: up to 25 items, each a string or `{requirement, category?, priority?, target?}` (`priority`: `must|should|nice_to_have`). When both inputs are given, supplied requirements are compared and CRM constraints/unknowns are still reported.
- `product_ids`: up to 6 catalog ids, compared in the order given. Omitted: candidates are derived from documented evidence (default 4, `max_candidates` 1-6), ranked by number of requirement areas with a documented capability, then `product_id`.
- `focus_areas`: restricts the comparison to areas such as `high_availability`, `disaster_recovery`, `capacity_scalability`, `encryption_at_rest`, `compliance_audit`, `centralized_management`, `migration_replacement`, `cyber_resilience`, `backup_retention`, `performance`.

`data`: `illustrative`, `notice`, `synthetic_customer_data`, `fit_status_legend`, `requirements_overview` (`functional`, `technical`, `unmapped`, `business_priorities`, `constraints`, `unknown_requirements`, `validation_questions`), `candidate_selection`, `candidates`, `comparison_matrix[]`, `side_by_side[]`, `product_summaries[]`, `requirements_not_yet_validated[]`, `recommended_discovery_questions[]`, `preliminary_solution_direction` (`worth_exploring`, `caveats`), `injection_warnings`. With `account_id`: `opportunity_id`, `account_id`, `opportunity_name`.

Each `comparison_matrix` row: `requirement_id`, `requirement`, `category`, `product_id`, `product_name`, `documented_capability[]`, `evidence_source` (`source_id`, `source_url`, `verified_date`), `verification_status`, `fit_status`, `missing_information[]`, `limitations[]`, `conflict`, `conflict_detail`, `rationale`.

Fit rules (deterministic, no inference):
- `Supported`: verified entry, a capability that matches the requirement area, every measurable qualifier in the requirement (hours, standards, `AES-256`, `HIPAA`, ...) present in the evidence text, no outcome claim ("reduce ..."), and a quantified target where the area needs one (capacity, performance).
- `Partially supported`: verified, relevant capability documented, but at least one of those conditions fails.
- `Not supported`: only from an explicit structured attribute (`structured_attributes.<area>.status = "not_supported"` with an `evidence` string) on a verified entry. Free-text limitations that sound negative are flagged in `missing_information` for specialist review, never converted to `Not supported`.
- `Unknown / insufficient evidence`: no documentation, an unmapped requirement, an unverified/synthetic entry (any `synthetic: true`, or missing `source_url`/`verified_date`), or conflicting catalog information (`conflict: true`).
- When no candidate is verified, `illustrative` is `true`, `notice` starts with `ILLUSTRATIVE ONLY`, and `worth_exploring` is empty.

No pricing, guaranteed recovery times, benchmarks or competitive claims are ever returned. Errors: `invalid_input` (missing inputs, malformed requirements/ids/areas, out-of-range `max_candidates`), `not_found` (unknown account/opportunity/`product_ids`, no requirement left after `focus_areas`, no catalog evidence, empty catalog). `product_ids` not found returns the valid ids in `suggestions`.

## Scheduled pipeline briefings (Feature 4)

These five tools are the **only** exception to the "all tools are read-only" convention above, and the only tools that write anything besides the Word export. They write to the scheduler state directory (`outputs/scheduler/`, git-ignored; override with `SALESFLOW_SCHEDULER_DIR`, absolute path) and never to `data/`. Implemented in `schedule_spec.py`, `schedule_store.py`, `pipeline_review.py`, `scheduler.py`; tool wrappers in `server.py`. Setup, lifecycle and limitations: [`docs/scheduled-briefings.md`](../scheduled-briefings.md).

Additional statuses used by these tools: `confirmation_required`, `confirmation_invalid`, `run_failed`, `scheduler_unavailable`.

**Seller authorization (two steps).** `create_pipeline_schedule` and `update_pipeline_schedule` never act on the first call. Called without `confirmation_token`, they change nothing and return `status: "confirmation_required"` with a `preview` and a single-use `confirmation_token`. Bob must show the preview to the seller and repeat the identical call with the token only after the seller explicitly approves. Tokens are bound to the exact parameters, expire after 10 minutes, and are spent on first use. A wrong, replayed, expired or mismatched token returns `confirmation_invalid` and changes nothing. Validation errors are returned before any token is issued.

### 6. `create_pipeline_schedule(name, cadence, hour, minute?=0, days_of_week?, timezone?="America/New_York", seller?, confirmation_token?)`

- `cadence`: `daily` or `weekly`. `days_of_week` is required for weekly (`mon`..`sun` or full names) and rejected for daily. `hour` 0-23 and `minute` 0-59 are **local** wall-clock time in `timezone` (any valid IANA name). `seller` optionally limits the review to one seller's deals (case-insensitive); omit for all sellers.
- DST: the local time is kept across transitions. A time that does not exist (spring forward) runs at the shifted wall-clock time that day; an ambiguous time (fall back) runs once, at its first occurrence. A schedule never runs twice or zero times in a local day.
- `data`: `schedule` (see below), `scheduler_process_running`, `limitation`.

`schedule` fields: `schedule_id` (`sched_` + 12 hex), `name`, `seller`, `status` (`active|paused|cancelled`), `enabled`, `cadence`, `days_of_week`, `time_local`, `timezone`, `description`, `next_expected_run`, `last_run`, `last_successful_run` (each `{utc, local}`), `last_run_status`, `created_at`.

### 7. `list_pipeline_schedules(include_cancelled?=false, history_limit?=5)`

Read-only. `data`: `schedules[]` (each with `recent_runs[]`: `run_id`, `trigger` `scheduled|manual`, `status` `running|success|failed|skipped`, `scheduled_for`, `started_at`, `finished_at`, `error_code`, `error_message`, `missed_occurrences`, `summary`), `count`, `scheduler_process` (`running`, `last_heartbeat_at`; `running` is true only if a daemon ticked in the last 2 minutes), `limitation`. `history_limit` 0-25.

### 8. `update_pipeline_schedule(schedule_id, action, confirmation_token?)`

`action`: `pause`, `resume`, `cancel`. Cancel is permanent (history is kept); a cancelled schedule cannot be changed. Resume recomputes the next run from now and does not replay missed runs. Errors: `invalid_input` (bad id/action, already paused/active/cancelled), `not_found`, `confirmation_invalid`.

### 9. `run_pipeline_review(schedule_id?, seller?)`

Runs a review immediately (recorded as a `manual` run) and stores the digest. Does not create or change a schedule and sends nothing. `data`: `run_id`, `summary` (`active_deals_analyzed`, `flagged_deals`, `high_risk`, `flagged_value`). On a CRM read failure: `status: "run_failed"` with a user-safe message and `error_code` (`crm_unavailable`, `crm_invalid`, `internal_error`); the failure is also recorded in history.

### 10. `get_latest_pipeline_digest(schedule_id?)`

Read-only. `data`: `run_id`, `generated_at`, `digest` (structured), `markdown`, `newer_unsuccessful_run` (set when a failed/skipped run is newer than this digest, so a failing schedule is not hidden), `limitation`. `not_found` if no successful run exists.

Digest structure: `summary` (active deals analysed, total value, flagged count/value, risk distribution, top risk factors, unknown-field counts), `flagged_deals[]` ranked by risk score then value (`rank`, `opportunity_id`, `account_name`, `stage`, `seller`, `value`, `close_date`, `risk_score`, `risk_rating`, `evidence[]`, `recommended_actions[]`, `unknown_factors[]`), `not_flagged_opportunity_ids`, `definitions`, `notes`, `disclaimer`, `limitations`. Scores come unchanged from the Feature 1 risk engine; missing fields are reported as Unknown and are not scored.

## Health check

`ping()` returns `{"status": "ok", "data": {"server": "salesflow", "version": "0.1.0"}}`. Retained for connection checks.

## Open items

- Lane C to confirm or adjust the playbook fixture schema above and deliver `data/playbooks/*.json`.
- Exact tool identifiers as exposed in Bob IDE (Lanes A and B): confirm after restarting the server in Bob.
