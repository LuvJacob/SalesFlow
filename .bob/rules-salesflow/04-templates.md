# 04 - Output templates

Use these formats consistently. Keep them tight. Omit a section only when its workflow was not requested, and say "Not requested" rather than silently dropping it from a full meeting brief. Apply the labels and citations from `03-grounding-safety.md` throughout.

Evidence tags in tables: **V** = Verified (cite source_id), **A** = Assumed, **U** = Unknown.

If MCP data was unavailable, add this line directly under the title: `Data status: MCP tools unavailable or no match - content is based on seller-provided information (unverified).`

## 1. Meeting brief

```
# Meeting Brief: <Company> - <meeting purpose>
Data status: <Retrieved via MCP: list tools called | MCP unavailable ...>
Synthetic data: <yes/no>   Prepared for: <seller>   Meeting: <date/length if known>

## 1. Meeting objective
<one or two sentences; mark as Assumed if inferred>

## 2. Account overview
| Item | Detail | Tag | Source |
|---|---|---|---|
| Industry | ... | V | src_... |
| Overview | ... | V | src_... |
| Known challenges | ... | V | src_... |

## 3. Opportunity snapshot
| Item | Detail | Tag | Source |
|---|---|---|---|
| Name / stage | ... | V | src_... |
| Requirements | ... | V | src_... |
| Stakeholders | roles | V | src_... |
| Prior notes | ... | V | src_... |

## 4. Verified / Assumed / Unknown
- **Verified:** ...
- **Assumed:** ... (reason)
- **Unknown:** ... (each becomes a question below)

## 5. SPIN discovery questions
<grouped S / P / I / N, 6-10 total, as defined in 02-spin.md>

## 6. Suggested agenda
<table from 02-spin.md, with desired outcome per segment>

## 7. Solution areas worth exploring
<table from template 3; "No supported match found" if empty>

## 8. Possible objections
<top 2-3 from template 4, each marked "Hypothetical"; only when asked or clearly relevant>

## 9. Information to obtain
- <each Unknown> - <who might know / how to ask>

## 10. Next steps for the seller
1. ...
```

## 2. Discovery agenda (standalone)

```
# Discovery Agenda: <Company> (<N> minutes)
Meeting goal: <...>   Attendees: <roles, if known; else Unknown>

| Time | Segment | Desired outcome | Key questions (numbers from SPIN list) |
|---|---|---|---|

Information to obtain: <list>
```

## 3. Solution recommendations

```
## Solution areas worth exploring (preliminary, not a validated configuration or quote)

| Customer need | Product / area | Why it may fit | Evidence (source_id, source_url, verified_date) | Limitations / validate |
|---|---|---|---|---|

- Entries marked synthetic: <list> - demo data, not a statement of real product capabilities.
- Needs with no supported match: <list>
- Validate with a specialist: sizing, configuration, compatibility, and commercial terms. No pricing is provided.
```

Each row's "why it may fit" must restate the matched requirement and use only wording supported by the tool result.

## 4. Objection-handling guide

```
## Objection: "<customer wording>"
Category: pricing | technical | competition | implementation | value      Status: Hypothetical | Raised by customer
Playbook source: <source_id or "none - general guidance, Assumed">

1. **Clarify first** (ask before answering)
   - <question>
   - <question>
2. **Acknowledge:** <one sentence that shows understanding>
3. **Respond:** <evidence-based points, each with a source or marked Assumed>
4. **Reframe / value:** <tie to the customer's stated requirements>
5. **Propose next step:** <low-pressure action>

Do not say: <unsupported claims to avoid, e.g. prices, competitor weaknesses>
```

For a pricing objection, do not quote or compare prices. Focus on clarifying what the customer is comparing, the scope, and the total value drivers they named.

## 5. Follow-up email draft

Use only facts the seller supplied from the meeting plus Verified data. Do not invent discussion points, commitments, dates, or attendees.

```
**DRAFT - for seller review. Not sent.**

Subject: <specific, short>

Hi <name or [Customer name]>,

Thank you for taking the time to meet on <date, or [date]>. 

What we heard
- <point from seller notes>
- <point>

How we can help (to explore, not a commitment)
- <area tied to a stated need; cite supported solution area only>

Proposed next steps
1. <action> - <owner> - <proposed date or [date]>
2. ...

Open questions
- <unknowns still to resolve>

<Closing line>
[Your name]

---
Seller checklist: confirm names and facts, remove anything you cannot stand behind, and check for sensitive details before sending.
```

Use bracketed placeholders for anything not provided. Offer revisions in tone, length, or content, and wait for the seller to approve.

## 6. Opportunity summary

```
# Opportunity Summary: <Opportunity name>
Account: <name> (<account_id>)   Stage: <stage>   Synthetic: <yes/no>

| Dimension | Status | Evidence |
|---|---|---|
| Business need | known / partial / unknown | ... |
| Budget | known / unknown | ... |
| Decision maker | known / unknown | ... |
| Technical requirements | known / partial / unknown | ... |
| Timeline | known / unknown | ... |

Gaps and next actions: <list>
```


## 7. Post-meeting deliverables

Use when the seller submits meeting notes or a transcript (Workflow 7). Build from the `analyze_meeting_notes` and `propose_crm_updates` tool results. Do not invent anything absent from the tools or seller-supplied text.

```
# Post-Meeting Summary: <Company> — <meeting date or [date]>
DRAFT — for seller review. Not sent. Synthetic data: <yes/no>

## 1. Executive summary
<2–4 sentences: meeting purpose, roles present (no invented names), headline outcome.>

## 2. Confirmed customer requirements
| # | Requirement | Confidence | Excerpt |
|---|---|---|---|
| 1 | ... | explicit / inferred | "..." |

## 3. Business challenges identified
| # | Challenge | Confidence |
|---|---|---|

## 4. Stakeholders and decision-makers
| Role | Name | Notes | Confidence |
|---|---|---|---|
| ... | [Unknown] | ... | explicit / inferred |

## 5. Customer objections
| Objection | Confidence |
|---|---|

## 6. Budget and timeline
| Signal | Detail | Confidence |
|---|---|---|
| Budget | ... | explicit / inferred / unknown |
| Timeline | ... | explicit / inferred / unknown |
| Dates found | ... | explicit |

## 7. Action items
| # | Action | Owner | Deadline | Confidence |
|---|---|---|---|---|
| 1 | ... | seller / [role] / [Unknown] | [date] | explicit / inferred |

## 8. Open questions
- <question or unknown that was not resolved in the meeting>

## 9. Suggested next meeting agenda
1. <topic based on open questions>
2. <topic based on unresolved requirements>
3. ...

## 10. Follow-up email draft
<use Template 5 above — include DRAFT marker>

## 11. Proposed CRM updates (for seller approval — not yet applied)
| Field | Proposed value | Excerpt | Uncertainty |
|---|---|---|---|
| requirements | ... | "..." | low / medium / high |
| stakeholders | ... | "..." | ... |
| next_meeting_scheduled | true | "..." | low |

<preservation_notice from tool result — confirm no changes have been made>
```

Each row's "excerpt" must be a direct quote from the meeting text (shortened if needed) or left blank. Never paraphrase a quote into something that was not said. Use `[Unknown]` for any missing field.


## 8. Solution comparison

Use for Workflow 8. Build every cell from the `compare_solutions` result. Do not add capabilities, figures or claims. Status words are the tool's own.

```
# Solution Comparison: <Company> - <opportunity name>
DRAFT - for seller review. Not sent.
Data status: Retrieved via MCP: compare_solutions   Synthetic customer data: <yes/no>   Illustrative only: <yes/no>
<data.notice, verbatim>

## 1. Requirements overview
| ID | Requirement | Type | Measurable targets | Source |
Business priorities / Constraints / Unknown requirements: <bullets from data.requirements_overview>

## 2. Side-by-side comparison
| Requirement | <Product A> | <Product B> | ... |      (cells: Supported / Partial / Not supported / Unknown)

## 3. Detailed matrix (only the rows the seller needs; offer the rest)
| Req | Candidate | Fit | Documented capability | Evidence (source_id, source_url, verified_date) | Missing information | Limitations |

## 4. Strengths and limitations
<per candidate: documented strengths with requirement ids, catalog limitations, any conflicts>

## 5. Requirements not yet validated
| Req | Requirement | Best result | Why | (also name other catalog products with documented evidence, if the tool lists them)

## 6. Recommended discovery questions
<numbered, grouped by requirement; keep the tool's wording>

## 7. Preliminary solution direction (worth exploring - not a validated fit)
<data.preliminary_solution_direction.worth_exploring, then every caveat>
```

Rules:
- Lead with a 2-3 sentence summary: how many requirements have a Supported candidate, how many remain unvalidated, and the largest gaps.
- A `Supported` cell still means "documented in the catalog", not "validated for this customer". Say so once.
- A target the tool lists as undocumented (for example a recovery time) must be called out as unconfirmed. Never state or imply a guaranteed recovery time, performance figure, price, ROI or competitive advantage.
- Mark the direction as preliminary and list the caveats. If the tool returns no `worth_exploring` entries, say no direction can be offered on current evidence.

## Length and style

- Lead with the answer. Use tables for facts, short bullets for actions.
- No filler, no emojis, no marketing language.
- For a quick question, answer briefly and skip the full template.
