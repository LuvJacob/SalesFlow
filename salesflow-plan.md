# SalesFlow Implementation Plan

## Top-Level Overview

**Goal:** Build SalesFlow, a single custom IBM Bob mode backed by a read-only Python MCP server serving synthetic CRM, product, and playbook data. Sellers use it entirely inside Bob's chat to produce grounded discovery preparation, solution positioning, objection guidance, and sales content.

**Source of truth:** [`PRD.md`](PRD.md) (stays at repo root). [`README.md`](README.md) is a blueprint and must be brought into line with the PRD.

**Locked decisions**
- Bob **IDE** is the target product (not Bob Shell).
- MCP server in **Python**, using **FastMCP** managed with **uv**, stdio transport.
- The mode may **save briefs** to `outputs/*.md` through a restricted `edit` group.
- No frontend, no multiagent, no subagents, no write access to data, no email sending.
- All data is synthetic or explicitly approved.
- PRD changes are **proposed in a separate document**; `PRD.md` is not edited silently.

**Approach:** Agree contracts first, prove the Bob-to-MCP link with a stub, then let four lanes work in parallel on disjoint files: mode and rules, MCP server, data and tests, support.

**Repository state at planning time:** only `PRD.md`, `README.md`, and `.git` (remote `https://github.com/LuvJacob/SalesFlow.git`, branch `main`). No `.bob/`, source, data, tests, dependency files, or `.gitignore`. `PRD.md` has uncommitted changes. Do not overwrite existing work.

### Bob capabilities (from Bob documentation) this plan relies on
- Project modes: `.bob/custom_modes.yaml`, top key `customModes:`; fields `slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions`, `groups`.
- IDE tool groups: `read`, `edit` (with `fileRegex`), `execute`, `mcp`, `skill`, `workflow`, `todo`, `subtask`, `subagent`, `mode`.
- Mode-specific instructions: `.bob/rules-{slug}/*.md`, loaded alphabetically and combined with `customInstructions`.
- Activation: the mode picker, or the slash command `/{slug}`.
- Project MCP config: `.bob/mcp.json`, key `mcpServers`; stdio fields `command`, `args`, `cwd`, `env`, `alwaysAllow`, `disabled`. Project config overrides global on name conflicts.
- MCP tools are invoked through `use_mcp_tool`. The "Use MCP Servers" setting is on by default. Per-tool toggles and "Always allow" live in Settings, MCP tab.

### Assumptions requiring validation (resolved in Sub-task 1)
- A1. Whether `fileRegex` is matched against workspace-relative paths.
- A2. Whether `cwd` in `.bob/mcp.json` accepts relative paths or a workspace variable; otherwise use an absolute path or a launcher script documented in setup.
- A3. How the MCP server name prefix appears when the mode instructions name tools.
- A4. Whether a project mode appears in the picker immediately or needs a window reload.
- A5. Whether uv is installed on hackathon machines, and which Python version it resolves.
- A6. Whether `alwaysAllow` gives a smooth demo with no approval prompts.
- A7. Latest stable FastMCP release and its maintenance status, license, and known vulnerabilities (security policy: latest stable, maintained within 6 months, no critical CVEs, lockfile required).

### Cross-cutting rules (apply to every sub-task)
- No secrets in the repo. MCP uses stdio only, with no network listener and no `0.0.0.0`.
- Tool input validation: type, length, and allowlist. Errors are generic structured objects with no stack traces. Logs are structured and never contain sensitive data.
- Tools never write to data. The only write permitted anywhere is the mode saving drafts under `outputs/`.
- Dependencies pinned through the uv lockfile, with a vulnerability scan before release.
- File ownership per lane (see Sub-task 9) to avoid merge conflicts.

---

## Sub-Tasks

### Sub-task 1: Contracts, repository hygiene, and Bob-to-MCP smoke test

- **Status:** [ ] pending
- **Intent:** Establish the shared contracts and prove that a custom mode and a Python stdio MCP server work together in Bob IDE before any real work depends on it. Resolve assumptions A1–A7.
- **Expected Outcomes**
  - `.gitignore` exists; the uv lockfile is committed.
  - A written contract fixes tool names, inputs, outputs, error shapes, record schemas, and `source_id` format.
  - A stub MCP tool is callable from a minimal SalesFlow mode in Bob IDE.
  - A teammate can reproduce this from the setup doc.
- **Todo List**
  1. Create `.gitignore` (Python, uv venv, `.env`, OS files, generated `outputs/` except a `.gitkeep` and one sample).
  2. Write `docs/contracts/mcp-tools.md`: the four tools (`get_account_profile`, `get_opportunity_context`, `search_product_knowledge`, `get_sales_playbook`), input limits, output JSON shape, `not_found` and `invalid_input` error shapes, an `unknowns` array on opportunities, and `source_id` and `verified_date` on product facts.
  3. Define record schemas for accounts, opportunities, products, and playbooks in the same document.
  4. Check the latest stable FastMCP (and the official MCP Python SDK as an alternative), its maintenance and license, and pick the version.
  5. Scaffold `mcp-server/` with uv (`pyproject.toml`, lockfile, `src` package) and one stub tool.
  6. Write a minimal `.bob/custom_modes.yaml` (`slug: salesflow`, groups `read`, `mcp`, restricted `edit`, per the `fileRegex` finding) and `.bob/mcp.json`.
  7. In Bob IDE: confirm the mode shows in the picker and via `/salesflow`; confirm the stub tool is listed and callable; record results for A1–A6.
  8. Write `docs/setup.md` with exact install, register, and verify steps.
- **Relevant Context:** [`PRD.md`](PRD.md) sections 7 and 10; [`README.md`](README.md); security rules for packages, secrets, and network binding.
- **Notes for the next sub-task:** record validated answers for A1–A7 here when done.

### Sub-task 2: PRD and README reconciliation proposal (no edits to `PRD.md`) — DO THIS FIRST

- **Status:** [x] done — proposal written to `docs/prd-revisions.md` (22 items, R-01 to R-22). Awaiting team approval before any edit to `PRD.md` or `README.md`.
- **Intent:** Surface the conflicts between the PRD, README, and locked decisions as a reviewable proposal rather than silent edits.
- **Expected Outcomes:** `docs/prd-revisions.md` lists each issue, its location, and the exact proposed wording, for team approval.
- **Todo List**
  1. Record each issue with location and proposed fix:
     - MCP described as optional, but mandatory for this MVP (PRD sections 1 and 7 against section 8).
     - Diagram shows 3 tools while the text lists 4; `get_sales_playbook` is missing from the diagram.
     - README tool names (`get_account`, `get_opportunity`, `get_interactions`, `search_solution_catalog`) differ from the PRD names.
     - The README acceptance criterion needs two or more tool calls while the PRD needs one; align to four tools and at least two distinct calls in the demo.
     - Demo timeline differs between PRD and README.
     - README structure uses `docs/PRD.docx`, an unconfirmed `.bob/` path, and optional `mcp-server`; update to the real structure.
     - "Approved documentation" is undefined; propose a catalog based on public IBM pages with source URL and verification date.
     - "JSON or SQLite" is undecided; propose JSON.
     - Success metrics have no measurement method.
     - Date field (October 29, 2026) needs confirmation.
     - Comparison and competitive positioning are listed as P1 or nice-to-have; propose playbook-only for the MVP.
  2. Add a section listing the proposed README rewrite points for the final documentation sub-task.
  3. Get team approval before any edit to `PRD.md` or `README.md`.
- **Relevant Context:** [`PRD.md`](PRD.md), [`README.md`](README.md).

### Sub-task 3: Mock enterprise data

- **Status:** [ ] pending
- **Intent:** Provide realistic, fully synthetic data that makes the account-specific grounding and missing-information behaviour demonstrable.
- **Expected Outcomes**
  - `data/` contains validated JSON data meeting the Sub-task 1 schemas.
  - Every product claim has a `source_id`, and every record carries `synthetic: true` where applicable.
- **Todo List**
  1. `data/accounts.json`: 3–4 fictional accounts, including Acme Healthcare, one sparse account to test missing data, and one in a different industry.
  2. `data/opportunities.json`: stage, requirements, stakeholders, prior meeting notes, with deliberate unknowns (budget, capacity, decision-makers) for Acme.
  3. `data/products.json`: a small catalog covering storage, high availability, disaster recovery, encryption and security, and hybrid cloud. Entries are hand-written summaries of public IBM pages with `source_url` and `verified_date`; anything unverified is flagged synthetic. Include `limitations` and `needs_validation` fields.
  4. `data/playbooks/`: SPIN guide, discovery agenda, qualification, and objection categories (pricing, technical capability, competition, implementation, business value), each with clarifying questions and approved talking points. Competitor entries contain no unsupported claims.
  5. Add one seeded post-meeting notes sample for the email demo.
  6. Add a deliberately poisoned fixture (a record containing instruction-like text) under `tests/` only, not in production data.
  7. Have the support contributor proofread for realism and typos.
- **Relevant Context:** Contract doc from Sub-task 1; PRD FR-04, FR-12–16, FR-19, FR-21; PRD section 9.

### Sub-task 4: MCP server implementation

- **Status:** [ ] pending
- **Intent:** Replace the stub with four read-only, validated tools reading the mock data.
- **Expected Outcomes**
  - The four tools behave as specified in the contract against the real data.
  - Invalid or unknown input yields structured, generic errors.
  - The server starts via `uv run` and registers in `.bob/mcp.json`.
- **Todo List**
  1. Implement a data loader that validates files against schemas at startup and fails clearly on bad data.
  2. `get_account_profile(company_name)`: normalised, tolerant match; returns `not_found` with suggestions when ambiguous.
  3. `get_opportunity_context(account_id)`: returns the opportunity and the explicit `unknowns` list.
  4. `search_product_knowledge(query)`: keyword search with ranked top-N, with `source_id` and `verified_date` in results.
  5. `get_sales_playbook(topic)`: allowlisted topics only.
  6. Input validation (type, length, allowed characters); generic errors; structured logging with no sensitive data; timeouts.
  7. Mark tools read-only in their metadata where FastMCP supports it; no filesystem writes anywhere in the server.
  8. Register all four tools in `.bob/mcp.json` with `alwaysAllow` per A6; remove the stub.
  9. Run a vulnerability scan on dependencies.
- **Relevant Context:** `docs/contracts/mcp-tools.md`; `data/`; PRD section 7 tool definitions; security rules on validation, error handling, and logging.

### Sub-task 5: Mode instructions and output templates

- **Status:** [ ] pending
- **Intent:** Encode SalesFlow's behaviour, so the mode routes requests, calls tools in the right order, structures its output, and refuses unsupported claims.
- **Expected Outcomes**
  - A complete `custom_modes.yaml` and `.bob/rules-salesflow/` files covering all five features.
  - Responses label every statement as Verified, Assumed, or Unknown, and cite `source_id`s for product claims.
- **Todo List**
  1. `custom_modes.yaml`: short `roleDefinition`, `whenToUse`, and `description`; groups `read`, `mcp`, and `edit` restricted by `fileRegex` to `outputs/*.md`. No `execute`, no `subagent`.
  2. `01-routing.md`: intent classification (account intelligence, discovery prep, positioning, objection, content), the tool-call order for a meeting prep request, and what to ask when the company, opportunity, or meeting objective is missing.
  3. `02-spin.md`: SPIN structure, 6–10 questions grouped by Situation, Problem, Implication, and Need-Payoff, and an agenda with desired outcomes and missing information to collect.
  4. `03-grounding-safety.md`: facts versus assumptions, citation rules, no pricing or discounts, no competitor claims without a playbook source, treat tool output as data and never as instructions, handle `not_found` without inventing, require seller review before any external use, and never send email.
  5. `04-templates.md`: meeting brief, agenda, objection card, opportunity summary, and follow-up email, each with a "draft: review before sending" marker.
  6. Define the file-save behaviour: only on the seller's request, only to `outputs/`.
  7. Verify that the tool names in the instructions match how Bob exposes them (A3).
- **Relevant Context:** PRD sections 5, 6, 9; FR-01 to FR-27; the Bob mode and rules documentation summarised above.

### Sub-task 6: Automated tests for the MCP layer

- **Status:** [ ] pending
- **Intent:** Provide deterministic evidence that the tools are correct, safe, and read-only.
- **Expected Outcomes:** A pytest suite that passes locally and from a clean clone.
- **Todo List**
  1. Data integrity: every record validates, every `source_id` resolves, product entries have source and date.
  2. Per tool: found, not found, ambiguous, empty, over-long, special-character, and injection-like input.
  3. Read-only guarantee: no write calls and no data changes after a tool run.
  4. Product search ranking against the gold table (requirement to expected product ids).
  5. Poisoned-fixture test: the server returns the text as data and does not alter structure.
  6. Document how to run the tests in `docs/setup.md`.
- **Relevant Context:** `mcp-server/`, `data/`, contract doc, security rules sections 7 to 11.

### Sub-task 7: Behaviour scenarios and end-to-end acceptance

- **Status:** [ ] pending
- **Intent:** Verify the mode itself. LLM output is non-deterministic, so use a written rubric and logged runs.
- **Expected Outcomes:** `tests/scenarios/` with scenarios, rubric, and a results log; a completed PRD acceptance checklist.
- **Todo List**
  1. Scenarios: the Acme happy path; sparse account; unknown company; ambiguous company; a missing meeting objective; price request; competitor-claim request; "send this email"; an injection attempt via data; a revision request; a post-meeting email from notes.
  2. Rubric items: correct tool calls, 6–10 SPIN questions with correct categories, facts versus assumptions labelled, citations present, no invented capability or price, no external action taken, and review reminder present.
  3. Gold table in `tests/gold/recommendations.md`: customer requirement to expected product ids; check Bob's recommendations against it.
  4. Run every scenario at least twice and log the transcript summary and pass or fail.
  5. Walk through PRD acceptance criteria 1 to 10 as a checklist.
  6. Feed failures back into rules and data (Sub-tasks 3 and 5); re-run.
  7. Time the Acme end-to-end run against the 60-second target (measured manually, documented as informational).
- **Relevant Context:** PRD sections 3, 9, 10; Sub-task 5 rules; Sub-task 4 server.

### Sub-task 8: Demo, documentation, and submission package

- **Status:** [ ] pending
- **Intent:** Package the work for judging.
- **Expected Outcomes:** A rehearsed 5-minute demo and a submission that runs from a clean clone.
- **Todo List**
  1. Write `docs/demo-script.md` using this timeline:
     - 0:00–0:30: the fragmented-tools problem.
     - 0:30–1:00: pick SalesFlow in Bob and show the MCP server connected with its four tools.
     - 1:00–2:00: Acme prompt; live `get_account_profile` and `get_opportunity_context` calls.
     - 2:00–3:00: grouped SPIN questions, then `search_product_knowledge` and a cited solution fit with labels.
     - 3:00–4:00: consolidated meeting brief, saved to `outputs/`; a price request showing the guardrail.
     - 4:00–4:30: follow-up email draft from seeded notes, with the review marker.
     - 4:30–5:00: how this extends Bob (persistent role and rules, real tool calls, grounded data) and future CRM integrations.
  2. Prepare a prompt library in `prompts/` and a fallback screen recording in case MCP fails live.
  3. Update `README.md` (after approval from Sub-task 2) with real setup instructions, tool names, structure, and examples.
  4. Write `docs/bob-feedback.md` (team feedback on Bob) and `docs/submission.md` (problem, solution, deliverables).
  5. Record the video; rehearse twice with a timer.
  6. Build the ZIP; verify a clean clone installs and the demo works using only `docs/setup.md`.
- **Relevant Context:** PRD sections 12 and 10; README's "Required hackathon deliverables".

### Sub-task 9: Team lanes and file ownership

- **Status:** [ ] pending (reference, applied across sub-tasks)
- **Intent:** Allow parallel work with minimal merge conflicts.
- **Lanes**

| Lane | Contributor | Owns | Sub-tasks |
|---|---|---|---|
| A: Mode and prompts | Full contributor 1 | `.bob/custom_modes.yaml`, `.bob/rules-salesflow/*`, `prompts/` | 5, plus demo script with C |
| B: MCP server | Full contributor 2 | `mcp-server/**`, `.bob/mcp.json`, `docs/contracts/` (reviewed by A) | 1 (scaffold), 4, 6 |
| C: Data and QA | Full contributor 3 | `data/**`, `tests/**` | 3, 7 |
| D: Support | Limited-availability contributor | `docs/bob-feedback.md`, proofreading, screenshots, timed rehearsals, scenario execution logs | low-risk parts of 3, 7, 8; no code or config edits |

- **Rules:** Contracts change only by agreement between A and B. Each lane works on a branch and merges through PR. Sub-task 1 is done jointly by A and B before the lanes diverge.

---

## Dependencies Between Sub-tasks

- 2 comes first (user instruction): the revisions proposal is reviewed before any implementation. Sub-task 1 starts after the team has reviewed `docs/prd-revisions.md`.
- 3 and 5 start after the contract in 1; 4 starts after 1 and needs draft data from 3.
- 6 follows 4; 7 follows 4 and 5.
- 8 follows 7 (the README update also needs 2).

## Open Items

- Confirm the validated results for assumptions A1–A7 (recorded in Sub-task 1).
- Confirm the source and verifier for the product catalog.
- Confirm the PRD date field.
