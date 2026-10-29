# Demo Script: Acme Healthcare Discovery Prep (5 minutes)

**Owner:** Lane D. **Status:** Draft. Written against the shipped mode, rules, and MCP tools. **Not yet rehearsed in Bob.** Update the "Expected" notes after the first real run, and replace any line that does not match what Bob actually does.

## Before you start (checklist)

- [ ] Bob IDE is open on the SalesFlow repository.
- [ ] The `salesflow` MCP server shows as connected in Bob's MCP panel (toggle off and on if not). See `docs/setup.md`, sections 4 and 6.
- [ ] **SalesFlow** mode is selected.
- [ ] Ask once beforehand: "List which SalesFlow tools you can use right now." Confirm the exact tool names Bob shows.
- [ ] Start from a fresh chat so earlier output does not carry over.
- [ ] Have the prompt below ready to paste.
- [ ] Decide the fallback: if MCP fails live, show the recorded video clip and say so.

## Known limits to avoid on stage

| Limit | Why it matters |
|---|---|
| `data/playbooks/*.json` may still be empty | `get_sales_playbook` then returns `not_found`. Do not promise playbook-backed objections until Lane C delivers the data. |
| Only Acme Healthcare is guaranteed in the data | Use Acme for the live demo. |
| Saving to `outputs/` is disabled in the mode | Do not ask Bob to save a file. Show the brief in chat. |
| Only one catalog product may exist, marked synthetic | Say "synthetic demo catalog". Do not present product facts as official IBM specifications. |

## Canonical prompt

> Prepare me for a discovery meeting with Acme Healthcare about modernizing their storage infrastructure. Retrieve the account and opportunity details, identify what we don't know yet, suggest solution areas supported by the product catalog, and generate 8 SPIN discovery questions plus a 30-minute agenda. Finish with a concise meeting brief. Distinguish verified information from assumptions and unknowns.

## Timeline

| Time | Say | Show | Evidence to point at |
|---|---|---|---|
| **0:00 to 0:30** | "Before a discovery call, a seller searches CRM, notes, product pages, and playbooks separately. It is slow, and the questions vary by person." | Title slide or the README problem section | n/a |
| **0:30 to 1:00** | "SalesFlow lives inside Bob. It is one custom mode plus a read-only MCP server. No separate website." | Mode selector with **SalesFlow** chosen. Bob's MCP panel with the `salesflow` server and its tools | Connected server, tool list |
| **1:00 to 2:00** | "I ask in plain language. Watch Bob call our tools instead of guessing." Paste the prompt. | Tool-call entries in chat for `get_account_profile` and `get_opportunity_context` | **Live MCP call 1 and 2.** Account `acct_acme_healthcare`, opportunity `opp_acme_storage_01`, stage Discovery |
| **2:00 to 3:00** | "Now it searches the product catalog and writes SPIN questions, grouped by Situation, Problem, Implication, Need-payoff." | `search_product_knowledge` call and the grouped questions | **Live MCP call 3.** Source IDs on product claims. Questions tied to Acme's requirements |
| **3:00 to 4:00** | "Everything is tagged Verified, Assumed, or Unknown. The opportunity has no budget, decision maker, or usable capacity recorded, so those become questions to ask." | The brief with V, A, U tags and the unknowns list | Unknowns match the tool result: budget, decision maker, usable capacity |
| **4:00 to 4:30** | "Guardrails: I ask for a discount." Type: *What discount can I offer Acme Healthcare?* | Bob declining and offering budget-discovery questions instead | Refusal with an alternative |
| **4:30 to 5:00** | "This extends Bob: a persistent sales mode, MCP tools over synthetic data, and the same pattern can later connect to approved CRM and product systems. Drafts are for the seller, nothing is sent." | Closing slide | n/a |

If time allows, replace the 4:00 beat with the follow-up email prompt from `prompts/example-prompts.md` (prompt 6). Check that the draft carries the "DRAFT - for seller review. Not sent." marker.

## What to say if asked

| Question | Honest answer |
|---|---|
| Is the data real? | No. It is fictional demo data, labelled synthetic. |
| Is this multi-agent? | No. One mode and one MCP server. |
| Does it send email or update the CRM? | No. Tools are read-only and drafts are for the seller to review. |
| Where do product claims come from? | Catalog entries with a source ID. Entries without a verified source are labelled synthetic. |
| What happens for an unknown company? | It reports that no record was found and asks for details. Example: *Prepare me for a meeting with Zephyr Dynamics Corp.* |

## Failure plan

| Failure | Response |
|---|---|
| MCP server disconnected | Toggle it off and on in Bob's MCP panel. If it stays down, switch to the recorded clip and say so. |
| Tools exist but names differ from the rules | Show Bob's tool list and tell Lane A. Do not rename anything live. |
| Output too long or off-format | Re-run once. If it fails again, use the recording. |
| Network or sign-in problem | Use the recording. |

## Rehearsal log

Fill in after each run.

| Run | Date | Total time | MCP calls seen | Problems | Fixed by |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

## Screenshot placeholders

Capture after a successful run. Do not commit screenshots containing anything other than synthetic data.

- [ ] Mode selector with SalesFlow selected
- [ ] MCP panel with `salesflow` connected and tools listed
- [ ] Tool call 1: account profile
- [ ] Tool call 2: opportunity context
- [ ] Tool call 3: product knowledge search
- [ ] SPIN questions section
- [ ] Brief with V, A, U tags
- [ ] Guardrail refusal (discount request)
