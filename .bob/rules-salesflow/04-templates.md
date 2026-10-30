# 04 - Output templates

Use these formats consistently. The standalone HTML report (Markdown as fallback) is the PRIMARY detailed output.
The `content` structures below are the same for HTML and Markdown.
The chat reply is a SHORT summary with a link to the report.

Evidence tags in tables: **V** = Verified (cite source_id), **A** = Assumed, **U** = Unknown.

If MCP data was unavailable, add this line directly under the title:
`Data status: MCP tools unavailable — content is based on seller-provided information (unverified).`

---

## Chat response style (all workflows)

After saving a report, the chat reply must be:
- **One short paragraph** (3–5 sentences max): headline finding, key insight, obvious next step.
- **A workspace-relative link** to the saved `.html` file (`workspace_relative_path`).
- **Open instructions**: "Click the link to open the file, then open it in your browser (right-click > Reveal in Finder, or paste the file:// URL)." Do not say a preview opened. For a Markdown fallback use ⇧⌘V (Ctrl+Shift+V).
- No repeated CRM facts, no long product descriptions, no technical MCP logs.

**Do not** generate a full brief in chat when a report has been saved. The report IS the brief.

---

## Template 1: Discovery Meeting Brief (report content)

Structure for the `save_salesflow_report` content passed as `report_type: discovery_brief`:

```
account:
  name, industry, overview, challenges[], unknowns[]
opportunity:
  name, stage, requirements[], stakeholders[], unknowns[]
spin_questions:
  - { category: Situation|Problem|Implication|Need-Payoff, question, purpose }
  (exactly 4 questions — one of each type — displayed in the report)
agenda:
  - { time_slot, segment, goal }
qualification_gaps:
  - { gap }   # short label only, e.g. "Budget Approval"
solution_positioning:
  products:
    - { name, category, source_url, verification_status }
    # Only official IBM product pages; no guessed URLs; show "Link unavailable" if absent
next_steps: [ action1, action2, action3 ]   # max 3
sources: [...]
synthetic: true
```

Report sections rendered:
1. **Account Snapshot** — compact table (company, industry, opportunity, stage) + one-line overview
2. **Discovery Questions (SPIN)** — exactly 4 questions, one of each type, short and natural
3. **30-Minute Meeting Agenda** — compact table (Time | Topic | Objective)
4. **Qualification Gaps** — short bold labels only: `**Gap Name (Unknown)**`
5. **Potential IBM Products** — three-column table: Product | Product Group | Official IBM Product Page
6. **Next Steps** — max 3 seller actions, numbered
7. **Sources** — compact source note + synthetic-data disclosure

SPIN quality rules (override 02-spin.md for the report):
- The full 6–10 question set from `02-spin.md` is correct for chat; the report shows 4 (one per type).
- Questions must be short, natural, relevant, and neutral — do not lead toward a specific IBM product.
- One question per type. Prefer questions that address documented unknowns.

Qualification gaps:
- Short label only: `**Budget Approval (Unknown)**`
- Do NOT include explanatory paragraphs in the primary report.

Product table columns (exactly):
| Product | Product Group | Official IBM Product Page |
- Use only `source_url` from `search_product_knowledge` results.
- If `source_url` is null or not an IBM URL, write "Link unavailable".
- Never construct or guess IBM product URLs.

---

## Template 2: Pipeline Intelligence Report (report content)

Structure for `report_type: pipeline_digest` or `deal_risk_assessment`:

```
digest or summary data from get_pipeline_summary + get_at_risk_deals
  or get_latest_pipeline_digest
```

Report sections rendered:
1. **Pipeline Metrics** — compact table (Active Deals, Total Value, Flagged, High/Medium/Low counts)
2. **Risk Distribution** — **Mermaid pie chart** (ALWAYS include; preserve fenced Mermaid block)
3. **Top At-Risk Opportunities** — compact table, top 3 only (Opportunity | Risk | Stage | Value | Recommended Action)
4. **Key Seller Priorities** — numbered list, max 3 items
5. Heuristic-risk disclaimer footer

Important:
- KEEP the Mermaid diagram. Do not remove it.
- Remove repetitive paragraphs that restate what the chart already shows.
- Do not imply background notifications were sent.

---

## Template 3: Post-Meeting Summary (report content)

Structure for `report_type: followup_plan`:

```
account_name, meeting_label, executive_summary[], meeting_analysis{...},
crm_proposals{proposed_updates[...]}, actions[], unknowns[], synthetic
```

Report sections:
1. **Meeting Summary** — 2–4 sentences (executive_summary or derived from requirements)
2. **Action Items** — compact table (Action | Owner | Deadline | Basis)
3. **Follow-Up Email Draft** — short, with DRAFT marker, placeholder names
4. **Proposed CRM Changes** — compact table (Field | Proposed Value | Uncertainty), NOT YET APPLIED note
5. **Remaining Unknowns** — short bold labels: `**Item (Unknown)**`

Do NOT include:
- Full supporting excerpts and confidence explanations in the primary report
- Invented owners, deadlines, or customer commitments
- Claims that the CRM was updated or emails were sent
- A pending meeting treated as a confirmed scheduled meeting

---

## Template 4: Solution Comparison Report (report content)

Structure for `report_type: solution_comparison`:

```
from compare_solutions result:
  candidates[], side_by_side[], comparison_matrix[], product_summaries[],
  requirements_not_yet_validated[], preliminary_solution_direction{}, notice, sources[]
```

Report sections:
1. **Recommendation Summary** — 2–3 sentences from `worth_exploring` + caveats
2. **Comparison Matrix** — full requirements × products table (Supported/Partial/Not supported/Unknown)
3. **Top Candidate Products** — top 2 only; official IBM product links; documented strengths (max 3); limitations (max 3)
4. **Technical Validation Gaps** — short bold labels: `**Requirement Name — Unknown / insufficient evidence**`
5. **Sources** — compact note + synthetic/illustrative disclosure

Do NOT:
- Show long feature descriptions or duplicate explanations
- Claim a capability is supported solely from marketing language
- Assert guaranteed recovery times, performance figures, or prices
- Mark reconciled fit statuses differently from what the tool returned

---

## Template 5: Follow-up email draft (standalone, in chat)

Used when no Markdown report is being created (e.g., just an email draft request):

```
**DRAFT - for seller review. Not sent.**

Subject: <specific, short>

Hi <name or [Customer name]>,

Thank you for taking the time to meet on <date, or [date]>.

What we heard
- <point>

How we can help (to explore, not a commitment)
- <area tied to a stated need; cite supported solution area only>

Proposed next steps
1. <action> - <owner> - <proposed date or [date]>

Open questions
- <unknowns still to resolve>

<Closing line>
[Your name]

---
Seller checklist: confirm names and facts, remove anything unsuitable before sending.
```

---

## Template 6: Scheduled Pipeline Digest (report content)

Structure for `report_type: pipeline_digest` with digest data:

Report sections:
1. **Pipeline Metrics** — compact table
2. **Risk Distribution** — Mermaid pie chart (PRESERVE)
3. **Opportunities Needing Attention** — compact table, flagged deals
4. **Recommended Actions** — max 3 bullet points
5. Execution timestamp + scheduler/delivery disclaimer

Disclaimer must state:
- Data is synthetic demo data (if applicable)
- Risk scores are heuristic-based, not statistically validated predictions
- No notification was sent; the digest was stored and retrieved on request

---

## Template 7: Objection handling (chat only, no report)

```
## Objection: "<customer wording>"
Category: pricing | technical | competition | implementation | value
Status: Hypothetical | Raised by customer

1. **Clarify first:** <question>
2. **Acknowledge:** <one sentence>
3. **Respond:** <evidence-based, each with a source or marked Assumed>
4. **Reframe / value:** <tie to customer's stated requirements>
5. **Propose next step:** <low-pressure action>

Do not say: <unsupported claims>
```

---

## Length and style

- Lead with the answer. Use tables for facts, short bullets for actions.
- No filler, no emojis, no marketing language.
- No technical MCP logs in the main report.
- For a quick question, answer briefly in chat — no template, no report.
- Full technical evidence is available in MCP tool responses for seller reference.
