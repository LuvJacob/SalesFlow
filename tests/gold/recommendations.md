# SalesFlow — Product Recommendations Gold Table

**Owner:** Lane C  
**Purpose:** Maps stated customer requirements to the expected product IDs from `data/products.json`. Use this to spot-check that Bob's solution recommendations are grounded in the catalog and match the right products for each need.

**How to use:** After running Scenario 1 or Scenario 11, compare Bob's recommended products against the Expected column. A match is correct if the product ID appears in Bob's output (even if described by name rather than ID). A miss is a product that should appear but does not.

---

## Gold table

| Customer requirement | Expected product ID(s) | Why |
|---|---|---|
| Replace aging storage / primary storage modernisation | `prod_flashsystem_5200`, `prod_flashsystem_7300` | Both are IBM all-flash storage systems for enterprise workloads |
| High availability / no single point of failure | `prod_flashsystem_5200`, `prod_flashsystem_7300`, `prod_spectrum_virtualize` | HyperSwap HA capability present in all three |
| Disaster recovery / replication | `prod_flashsystem_5200`, `prod_flashsystem_7300`, `prod_spectrum_virtualize` | Synchronous/asynchronous replication in all three |
| Encryption at rest / HIPAA compliance | `prod_flashsystem_5200`, `prod_flashsystem_7300`, `prod_guardium_data_protection` | FIPS 140-2 encrypted drives; Guardium for audit trails |
| Backup and long-term retention | `prod_spectrum_protect`, `prod_cloud_object_storage` | Spectrum Protect for backup; COS for archival targets |
| Data audit trails / regulatory compliance | `prod_guardium_data_protection` | Real-time monitoring and tamper-proof audit trails |
| Heterogeneous storage / migrate existing arrays | `prod_spectrum_virtualize` | Virtualises third-party storage arrays non-disruptively |
| Ransomware resilience / cyber recovery | `prod_flashsystem_7300` | Built-in ransomware detection; Safeguarded Copy |
| Scalable object storage / archive | `prod_cloud_object_storage` | Petabyte-scale; S3-compatible; lifecycle policies |

---

## Scoring guidance

**Full match:** All expected product IDs for the requirement appear in Bob's output.  
**Partial match:** At least one expected product appears; others are missing.  
**Miss:** No expected product appears; Bob either recommended nothing or recommended a product not in the catalog.  
**Hallucination:** Bob recommended a product that does not exist in `data/products.json`.

A result is acceptable for the demo if:
- Acme's HA + DR requirements surface `prod_flashsystem_5200` or `prod_flashsystem_7300` plus `prod_spectrum_virtualize`
- Encryption / HIPAA surfaces at least one of `prod_flashsystem_5200`, `prod_flashsystem_7300`, or `prod_guardium_data_protection`
- No product IDs appear that are not in `data/products.json`
- No prices or unsupported capability claims appear alongside the recommendations

---

## Known limitations

- `prod_spectrum_virtualize` depends on stopword filtering and prefix stemming in the search function; queries using "virtualisation" or "migrate" may or may not surface it depending on query wording. Test with short keyword queries ("storage virtualisation", "migration") to confirm.
- `prod_guardium_data_protection` is categorised as "data security" not "storage" — it will not appear in generic "storage" searches. It should appear for queries containing "compliance", "audit", "HIPAA", or "encryption".
- Product catalog search returns a maximum of 5 results. If all 5 slots are occupied by storage entries, Guardium may not appear unless the query is targeted.
