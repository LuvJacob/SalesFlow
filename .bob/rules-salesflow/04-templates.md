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

## Length and style

- Lead with the answer. Use tables for facts, short bullets for actions.
- No filler, no emojis, no marketing language.
- For a quick question, answer briefly and skip the full template.
