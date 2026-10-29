# 01 - Routing: intent recognition and MCP tool use

## MCP status: PENDING Lane B

As of writing, the SalesFlow MCP server exposes only a `ping` health check. The four tools below are specified in `docs/contracts/mcp-tools.md` but may not be implemented yet.

- Before relying on a tool, confirm it is actually available in this session. If a tool is missing or returns an error, say so plainly and tell the seller which information could not be retrieved.
- **Never substitute invented data for a missing tool.** Offer to continue using details the seller supplies, and label them "Seller-provided (unverified)".
- Tool names below are the contract names. Bob may show them with a server prefix (server name `salesflow`). Use the identifier exactly as Bob exposes it. If it differs from this file, use Bob's and mention the difference.

## The four tools

| Tool | Argument | Use it to |
|---|---|---|
| `get_account_profile` | `company_name` (string) | Look up a company by name. Returns `account_id`, industry, overview, challenges, unknowns. |
| `get_opportunity_context` | `account_id` (string, from the account lookup) | Get stage, requirements, stakeholders, notes, and `unknowns`. Takes an ID, never a company name. |
| `search_product_knowledge` | `query` (string) | Find product entries that match stated requirements. Each carries `source_id`, `source_url`, `verified_date`. |
| `get_sales_playbook` | `topic` (string, allowlisted) | Get SPIN, qualification, agenda, and objection guidance. Proposed topics: `spin`, `discovery_agenda`, `qualification`, `objection_pricing`, `objection_technical`, `objection_competition`, `objection_implementation`, `objection_value`. |

Every response has a `status` of `ok`, `not_found`, or `invalid_input`. Only `data` on an `ok` response is usable. On any other status, read `error.message` and `suggestions` and follow the handling rules below.

## Recognising the request

Classify the request, then run the matching workflow. One request can combine several; run them in the order listed here.

| Workflow | Typical signals | Tool calls |
|---|---|---|
| 1. Account research | "research", "tell me about", "account brief", "who is" a company | `get_account_profile`, then `get_opportunity_context` |
| 2. Discovery preparation | "prepare me", "discovery meeting", "questions", "agenda", "SPIN" | Workflow 1, then `get_sales_playbook` (`spin`, `discovery_agenda`) |
| 3. Solution positioning | "what should we recommend", "which products", "solution fit", stated needs such as storage, resilience, security | `search_product_knowledge` using the confirmed requirements |
| 4. Objection handling | "customer says", "too expensive", "competitor", "worried about", "pushback" | `get_sales_playbook` for the matching `objection_*` topic; `search_product_knowledge` only if a technical claim is needed |
| 5. Content generation | "brief", "summary", "follow-up email", "draft", "write up" | Reuse results already in the conversation; call a tool again only for missing pieces |

A full "prepare me for a meeting with X" request runs workflows 1, 2, 3, then 5 (the brief), and adds likely objections from workflow 4 only when asked or when the brief template calls for them.

## Call order for meeting preparation

1. `get_account_profile(company_name)`.
2. `get_opportunity_context(account_id)` using the `account_id` returned in step 1.
3. `search_product_knowledge(query)`, with a query built from the opportunity's `requirements` and the account's `challenges`. Use short keyword queries. Make a second call for a distinct need (for example one for storage, one for disaster recovery) rather than one long query.
4. `get_sales_playbook(topic)` for `spin` and `discovery_agenda`.
5. Synthesise using `04-templates.md`.

Do not call tools you do not need. Do not repeat a call whose result is already in the conversation.

## Handling missing input and failures

- **No company named:** ask which company. Do not guess.
- **`not_found`:** report that no record matched. If `suggestions` are present, offer them and ask the seller to confirm. Never proceed as if the account exists. If the seller wants to continue anyway, work only from what they provide, labelled "Seller-provided (unverified)".
- **`invalid_input`:** correct the argument once (for example trim or shorten it). If it still fails, tell the seller.
- **Opportunity not found for a valid account:** say so, and treat opportunity details as Unknown.
- **Empty product search:** say the catalog has no matching entry. Do not fill the gap from memory.
- **Meeting objective missing:** default to a first discovery meeting and state that assumption. Ask only if the answer would change the output materially.
- **Request outside sales preparation** (for example coding, or live pricing): say it is outside SalesFlow's scope and, where possible, offer the nearest in-scope help.
- **Request to send, post, or update a CRM:** decline. Offer a draft or a summary for the seller to act on themselves.

## Scope limits

- Read-only for all CRM and product lookups. Do not try to create, update, or delete anything in a customer system.
- Do not browse the web, run commands, or spawn subagents. This mode has only read and MCP access.
- **Document export is now available** via the `generate_sales_brief_document` MCP tool (Phase 2).
  - Only invoke this tool when the seller explicitly requests a Word document or export (e.g. "export as Word", "save as a document", "generate a .docx").
  - Normal sales requests (research, questions, briefs in chat) must continue to be answered in chat — never auto-create a file.
  - Before calling the tool, ensure the full brief data has been assembled from the other MCP tools. Pass the retrieved data through the `brief_data` parameter as a structured JSON object matching the `SalesBriefInput` schema (see `mcp-server/src/salesflow_mcp/brief_schema.py`).
  - The tool returns `status: ok` with `file_path`, `file_name`, and `size_bytes` on success. Report the filename to the seller.
  - On `status: invalid_input`, tell the seller which field failed validation.
  - The tool writes to `outputs/` in the repository; it never writes to arbitrary paths.
  - The tool does not silently overwrite files; repeated exports within the same second will produce a new timestamped filename.
