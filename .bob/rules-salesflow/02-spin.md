# 02 - SPIN Selling

Use SPIN whenever you generate discovery questions or a discovery agenda.

## Definitions

| Type | Purpose | Style |
|---|---|---|
| **Situation** | Establish current facts and environment. | Factual and brief. |
| **Problem** | Uncover difficulties, dissatisfaction, and risks. | Open, about pain. |
| **Implication** | Draw out the consequences and cost of the problems. | Links a problem to business, clinical, financial, or operational impact. |
| **Need-Payoff** | Get the customer to state the value of solving it. | Asks what a solution would enable. |

## Quantity and balance

- Produce **6 to 10 questions** in total. If the seller asks for a specific number in that range, use it. If they ask for a number outside it, say you are keeping within 6 to 10, or explain the difference.
- Include **at least one** question of each type. A good spread for 8 questions is 2 Situation, 2 Problem, 2 Implication, 2 Need-Payoff.
- Keep Situation questions to the minimum. Do not ask for anything the account or opportunity record already tells you. Use it as context instead ("I understand you are replacing aging storage - ...").

## Grounding the questions

Build questions from retrieved data, not generic templates:

1. **Opportunity `requirements`** and the **account `challenges`** drive Problem and Implication questions.
2. **Opportunity `unknowns`** (budget, decision maker, usable capacity, and so on) must each be covered by at least one question, and listed in the brief's "Information to obtain" section.
3. The `spin` playbook from `get_sales_playbook` supplies the approved methodology wording. Follow it where it conflicts with this file about wording, but not about the safety rules in `03`.
4. Product areas supported by `search_product_knowledge` can inspire Need-Payoff questions. Do not mention a specific product capability inside a question as if it were settled. Ask about the customer's need instead.

If the account or opportunity could not be retrieved, write the questions from what the seller told you, mark the brief "based on seller-provided information", and keep them general to the stated industry and need.

## Question quality

- One idea per question. Open-ended (start with what, how, which, tell me about). Avoid yes or no except to confirm a fact.
- Questions are for the customer's own words. Do not lead them to a product.
- Never put a price, a discount, or an unsourced competitor claim in a question.
- Healthcare or other regulated industries: you may ask about compliance, availability, and recovery expectations, but do not claim any certification or regulatory fit for a product unless a tool result states it.

## Output format for questions

Group by type. Number continuously. After each question add a short italic purpose, and tag which unknown it addresses, if any.

```
### Situation
1. <question>  *Purpose: ...*
### Problem
2. <question>  *Purpose: ... (covers unknown: budget)*
### Implication
...
### Need-Payoff
...
```

## Discovery agenda

When an agenda is requested (default 30 minutes), use the `discovery_agenda` playbook if available, otherwise this skeleton, and adapt the times:

| Time | Segment |
|---|---|
| 0-3 min | Introductions and agreed meeting goal |
| 3-10 min | Situation |
| 10-18 min | Problem and Implication |
| 18-24 min | Need-Payoff and success criteria |
| 24-28 min | Qualification gaps (budget, decision process, timeline) |
| 28-30 min | Recap and next steps |

Each segment states its desired outcome. Scale the minutes for other meeting lengths.
