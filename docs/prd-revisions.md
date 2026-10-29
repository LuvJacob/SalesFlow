# SalesFlow — Proposed PRD and README Revisions

**Status:** Proposal for team review. `PRD.md` and `README.md` have **not** been edited. Nothing here takes effect until the team approves it.

**Basis:** Locked MVP decisions: Bob IDE; one custom mode; a custom Python (FastMCP + uv) read-only MCP server; synthetic data only; no frontend, multiagent, or subagents; the mode may save drafts to `outputs/*.md`.

Line references are to [`PRD.md`](../PRD.md) and [`README.md`](../README.md) as they stand today.

## How to review

For each item, mark **Approve**, **Reject**, or **Modify**. Approved items are applied in one pass by the documentation owner. Severity: **High** conflicts with a locked decision or blocks implementation; **Medium** causes inconsistency; **Low** polish.

---

## A. Conflicts with locked architecture decisions

### R-01 — MCP is described as optional (High)
- **Where:** PRD line 19 ("optional Model Context Protocol (MCP) integrations"), line 39 ("optional external integrations"); README line 10 and line 99 ("Add read-only MCP endpoints if supported by the event environment"), line 83 ("Optional read-only integration").
- **Conflict:** The PRD's own must-have list (line 337) and the locked decision require a working MCP server.
- **Proposed wording (PRD line 19):** "The solution leverages IBM Bob's custom mode functionality and a required, read-only Model Context Protocol (MCP) server to retrieve information from approved synthetic sources."
- **Proposed wording (README line 99):** "4. **Integration:** Build and register the read-only MCP server (required for the MVP)."
- Make the same change at PRD line 39 and README lines 10 and 83.

### R-02 — Architecture diagram omits a tool (High)
- **Where:** PRD lines 279–284 list three boxes: Account Lookup, Product Documentation Search, Opportunity Context Retrieval.
- **Conflict:** PRD lines 308–324 define four tools. `get_sales_playbook` is missing, and the playbook data is a core input to objection handling and SPIN.
- **Proposed change:** Add `|-- Sales Playbook Retrieval` under the SalesFlow MCP Server box, and add "Sales playbooks" to the data-source box.

### R-03 — MCP tool names disagree between documents (High)
- **Where:** README lines 64–69 use `get_account`, `get_opportunity`, `get_interactions`, `search_solution_catalog`. The PRD (lines 310–322) uses `get_account_profile`, `get_opportunity_context`, `search_product_knowledge`, `get_sales_playbook`.
- **Proposal:** The PRD names are canonical. Replace the README table with:

| Tool | Purpose |
|---|---|
| `get_account_profile(company_name)` | Retrieve a fictional account profile from the mock CRM. |
| `get_opportunity_context(account_id)` | Return opportunity details, requirements, meeting notes, and explicit unknowns. |
| `search_product_knowledge(query)` | Find curated product facts with source references. |
| `get_sales_playbook(topic)` | Retrieve discovery, SPIN, qualification, and objection guidance. |

- Also drop "Illustrative" and "proposed tools" wording (README lines 62, 71) once the tools exist.
- `get_interactions` has no PRD equivalent. Prior meeting notes are served inside `get_opportunity_context` (PRD line 314 already says it returns meeting notes).

### R-04 — Data store choice left open (Medium)
- **Where:** PRD line 303 ("JSON files or SQLite").
- **Proposal:** "JSON files". Reasons: diffable in PRs, no native dependency, easy for the support contributor to proofread, and no merge conflicts beyond text.

### R-05 — README repository structure does not match the decided layout (Medium)
- **Where:** README lines 75–88.
- **Conflicts:** It shows `.bob/` as "confirm version-specific path", `mcp-server/` as "Optional", `docs/PRD.docx` (the PRD is `PRD.md` at the root), and no `tests/` or rules directory.
- **Proposed replacement:**

```text
SalesFlow/
├── README.md
├── PRD.md
├── .gitignore
├── .bob/
│   ├── custom_modes.yaml
│   ├── mcp.json
│   └── rules-salesflow/
├── mcp-server/            # Python, FastMCP, uv
├── data/                  # accounts, opportunities, products, playbooks
├── prompts/
├── tests/
├── outputs/               # drafts saved by the mode
└── docs/
```

- Path details verified in the Bob documentation: project modes in `.bob/custom_modes.yaml`, MCP in `.bob/mcp.json`, mode rules in `.bob/rules-{slug}/`.

### R-06 — Mode write capability is unspecified (Medium)
- **Where:** PRD §7 and §9 do not say whether the mode can write files. PRD line 326 says "read-only" for the MCP tools.
- **Proposal:** Add to PRD §7 after line 326: "The SalesFlow mode may save generated drafts only to `outputs/*.md`, when the seller asks. It has no command execution and cannot modify data files or MCP data."

---

## B. Inconsistencies between PRD and README

### R-07 — MCP success criteria differ (Medium)
- **Where:** PRD line 58 ("at least one functional read-only integration"); PRD line 377–379 (account and product retrieval); README line 108 ("at least two successful read-only calls").
- **Proposal:** PRD metrics row becomes "Four functional read-only tools; at least two distinct tools called live in the demo." The README criterion is updated to match.

### R-08 — Demo timelines differ (Medium)
- **Where:** PRD lines 401–409 against README lines 113–119.
- **Proposal:** Adopt the following in both documents:

| Time | Demonstration |
|---|---|
| 0:00–0:30 | The fragmented-tools problem |
| 0:30–1:00 | Select SalesFlow in Bob; show the MCP server and its four tools |
| 1:00–2:00 | Acme Healthcare request; live account and opportunity retrieval |
| 2:00–3:00 | Grouped SPIN questions; product search and cited solution fit |
| 3:00–4:00 | Consolidated meeting brief saved to `outputs/`; guardrail demo (price request) |
| 4:00–4:30 | Follow-up email draft with review marker |
| 4:30–5:00 | How this extends Bob; future integrations |

### R-09 — Feature priority labels differ (Low)
- **Where:** README lines 34–43 list "Mock CRM MCP" and "Catalog lookup" as P1, while the PRD makes them must-have.
- **Proposal:** Promote both to P0, and rename "Catalog lookup" to "Product knowledge search".

### R-10 — Competitive positioning scope (Medium)
- **Where:** README line 42 ("Comparison", P1); PRD line 342 (nice-to-have "Competitive positioning research"), yet Feature 4 title includes "Competitive Positioning" and PRD line 321 handling.
- **Proposal:** For the MVP, competition is handled only through objection-playbook entries, with no competitor claims beyond what a playbook source supports (FR-21). Remove "Comparison" from the README table, or move it to nice-to-have.

---

## C. Missing definitions

### R-11 — "Approved documentation" is undefined (High)
- **Where:** PRD lines 47, 92, 136, 196.
- **Proposal:** Add a definition to PRD §9: "For the MVP, approved product information is a hand-written catalog of summaries of public IBM documentation. Every entry has a source URL and a verification date. Entries that cannot be verified are marked synthetic and cannot be presented as product facts. A named team member verifies each entry." (Owner: to be named.)

### R-12 — "Verified", "assumed", "unknown" are not defined (High)
- **Where:** FR-04 (line 96), acceptance criterion 6 (line 380).
- **Proposal:** Add to PRD §9: "**Verified:** returned by an MCP tool, with a source id. **Assumed:** inferred by SalesFlow and labelled as an assumption. **Unknown:** not available from any tool, and listed as information to obtain from the customer."

### R-13 — No tool or data contract (High)
- **Where:** PRD §7 lists tool names only.
- **Proposal:** Add to PRD §7: "Tool inputs, outputs, error shapes, and data schemas are specified in `docs/contracts/mcp-tools.md`, which is the authority for implementation." The file is produced in Sub-task 1.

### R-14 — Success metrics have no measurement method (Low)
- **Where:** PRD lines 53–60.
- **Proposal:** Add "Measured manually with a stopwatch in the demo environment; informational, not pass/fail" to the account brief timing row, and "Counted in the output by the QA rubric" to the question-count row.

### R-15 — Prompt-injection handling needs a test, not just a principle (Medium)
- **Where:** PRD line 368 ("Treat externally retrieved content as data, not trusted instructions").
- **Proposal:** Add an acceptance criterion: "11. A record containing instruction-like text is shown as data and does not change the mode's behaviour."

### R-16 — No acceptance criterion for refusing unsupported requests (Medium)
- **Where:** PRD §10.
- **Proposal:** Add: "12. Requests for prices, discounts, unsupported competitor claims, or sending email are declined with an explanation and an alternative."

### R-17 — Missing-data behaviour is not required in acceptance criteria (Medium)
- **Proposal:** Add: "13. For an unknown company, the mode reports that no record was found, and asks for details instead of inventing any."

---

## D. Housekeeping

### R-18 — Date field (Low)
- **Where:** PRD line 9 and README line 4 both say "October 29, 2026".
- **Action:** Confirm the date is correct, or correct it.

### R-19 — Reference to a non-existent PRD path (Low)
- **Where:** The kick-off notes assumed `docs/SalesFlow_PRD.md`; README line 145 says "the accompanying SalesFlow PRD".
- **Proposal:** Link it: "See [`PRD.md`](PRD.md)". The PRD stays at the repository root.

### R-20 — README setup note (Low)
- **Where:** README line 99 says the file describes a blueprint, not runnable code.
- **Proposal:** Keep it until Sub-task 8; then replace it with real install and run commands from `docs/setup.md`.

### R-21 — Technology stack table is incomplete (Low)
- **Where:** PRD lines 297–306.
- **Proposal:** Replace "Python or TypeScript" with "Python (FastMCP, managed with uv, stdio transport)", add "Bob IDE" under AI Interface, and add "pytest" as test framework.

### R-22 — Workstream names (Low)
- **Where:** PRD lines 388–393 list four workstreams; README lines 124–126 list three.
- **Proposal:** Use the four lanes in `salesflow-plan.md` (Mode and prompts; MCP server; Data and QA; Support) in both documents.

---

## Summary

| Severity | Items |
|---|---|
| High | R-01, R-02, R-03, R-11, R-12, R-13 |
| Medium | R-04, R-05, R-06, R-07, R-08, R-10, R-15, R-16, R-17 |
| Low | R-09, R-14, R-18, R-19, R-20, R-21, R-22 |

## Items needing a team decision

1. Who verifies the product catalog (R-11)?
2. Are the new acceptance criteria 11–13 accepted (R-15 to R-17)?
3. Is the publication date correct (R-18)?
4. Is competitive positioning deferred to playbook-only for the MVP (R-10)?
