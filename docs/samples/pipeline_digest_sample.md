# Pipeline risk briefing: Demo: Monday 8 AM ET pipeline risk briefing

- Generated: 2026-10-29T17:00:59-04:00 (America/New_York); UTC 2026-10-29T21:00:59+00:00
- Trigger: scheduled  |  Run: `run_fc1417344d39`
- Seller scope: All sellers
- Data: SYNTHETIC demo CRM data

## Summary

- Active deals analysed: 6 ($1,250,000)
- Flagged deals (Medium/High risk): 5 ($1,000,000)
- High Risk: 3 deal(s), $380,000
- Medium Risk: 2 deal(s), $620,000
- Low Risk: 1 deal(s), $250,000

Top risk factors:
- Missing next meeting: 3 deal(s)
- Missing budget confirmation: 2 deal(s)
- Missing decision-maker: 2 deal(s)
- No recent customer activity: 2 deal(s)
- Overdue closing date: 1 deal(s)
- Stalled opportunity stage: 1 deal(s)
- Unresolved requirements: 1 deal(s)
- Upcoming closing date: 1 deal(s)

## Flagged deals, highest risk first

### 1. Acme Healthcare: Acme Healthcare storage modernization

- Rating: **High Risk** (score 7)
- Opportunity: `opp_acme_storage_01`  |  Stage: Discovery  |  Seller: Bob
- Value: $150,000  |  Close date: 2026-12-15

Supporting evidence:
- Missing budget confirmation (+3): Budget confirmation is missing or listed as an unknown qualification detail.
- Missing decision-maker (+3): Decision-maker has not been identified or is listed as an unknown qualification detail.
- Missing next meeting (+1): No next meeting or follow-up is currently scheduled with the customer.

Recommended seller actions:
1. Introduce SPIN Need-Payoff and qualification questions to clarify the IT budget envelope and approval steps.
2. Identify the economic buyer and key stakeholders in the purchasing committee and establish engagement.
3. Reach out to the customer to schedule the next logical step, such as a technical deep-dive or follow-up session.

### 2. Apex Retail: Apex Retail Disaster Recovery Modernization

- Rating: **High Risk** (score 6)
- Opportunity: `opp_inactive_01`  |  Stage: Discovery  |  Seller: Bob
- Value: $180,000  |  Close date: 2026-11-15

Supporting evidence:
- No recent customer activity (+3): Last customer contact was 45 days ago
- Upcoming closing date (+1): Target close date (2026-11-15) is in 17 days
- Missing next meeting (+1): No next meeting or follow-up is currently scheduled with the customer.
- Stalled opportunity stage (+1): Opportunity is flagged as stalled in the CRM.

Recommended seller actions:
1. Reach out immediately to reconnect, check-in on project status, or schedule a quick sync.
2. Validate procurement, legal review, and signature steps to ensure timely execution.
3. Reach out to the customer to schedule the next logical step, such as a technical deep-dive or follow-up session.
4. Review opportunity strategy, offer additional value to the client, or multi-thread the engagement.

### 3. Nova Tech: Nova Tech Fast Dev Environment Storage

- Rating: **High Risk** (score 6)
- Opportunity: `opp_sparse_01`  |  Stage: Qualification  |  Seller: Charlie
- Value: $50,000  |  Close date: 2026-12-10

Supporting evidence:
- Missing budget confirmation (+3): Budget confirmation is missing or listed as an unknown qualification detail.
- Missing decision-maker (+3): Decision-maker has not been identified or is listed as an unknown qualification detail.

Recommended seller actions:
1. Introduce SPIN Need-Payoff and qualification questions to clarify the IT budget envelope and approval steps.
2. Identify the economic buyer and key stakeholders in the purchasing committee and establish engagement.

### 4. Summit Finance: Summit Finance Core Storage Refresh

- Rating: **Medium Risk** (score 3)
- Opportunity: `opp_overdue_01`  |  Stage: Negotiation  |  Seller: Alice
- Value: $420,000  |  Close date: 2026-10-15

Supporting evidence:
- Overdue closing date (+3): Target close date (2026-10-15) has passed by 14 days

Recommended seller actions:
1. Update the projected close date in the CRM and confirm the client's current procurement timeline.

### 5. Meridian Financial Services: Meridian Financial Services backup modernisation

- Rating: **Medium Risk** (score 3)
- Opportunity: `opp_meridian_backup_01`  |  Stage: Qualification  |  Seller: Alice
- Value: $200,000  |  Close date: 2027-02-28

Supporting evidence:
- No recent customer activity (+1): Last customer contact was 24 days ago
- Missing next meeting (+1): No next meeting or follow-up is currently scheduled with the customer.
- Unresolved requirements (+1): Unresolved requirements detected: regulatory deadline, economic buyer

Recommended seller actions:
1. Schedule a routine check-in or send a relevant product update to maintain momentum.
2. Reach out to the customer to schedule the next logical step, such as a technical deep-dive or follow-up session.
3. Clarify requirements through technical discovery and map them to verified product solutions.
4. Confirm missing CRM fields (not scored as risk): budget_confirmed, decision_maker_identified.

Unknown (not scored): budget_confirmed, decision_maker_identified

## Not flagged (Low Risk)

- `opp_healthy_01`

## Scope and limits

Risk scores come from transparent heuristic rules for prioritisation. They are not statistically validated or machine-learning predictions. Missing CRM fields are reported as Unknown and are not treated as negative evidence.

This digest is generated by a local scheduler that only runs while its host machine and the scheduler process are running. It is stored on disk for Bob to retrieve; it is not pushed into Bob and no message has been sent.
