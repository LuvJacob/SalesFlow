# Solution Comparison: Acme Healthcare - Acme Healthcare storage modernization

DRAFT - for seller review. Not sent.
Data status: Retrieved via MCP `compare_solutions` (account `acct_acme_healthcare`, opportunity `opp_acme_storage_01`). Synthetic customer data: yes. Illustrative only: no (candidates are verified catalog entries).

This comparison uses only documented catalog text. It contains no pricing, no guaranteed recovery times, no performance benchmarks and no competitive claims. It is a preliminary aid for seller and solutions-engineer review, not a validated configuration or quote.

Candidate selection: `derived_by_documented_category_overlap`.

## 1. Requirements overview

| ID | Requirement | Type | Area | Measurable targets | Source |
|---|---|---|---|---|---|
| REQ-1 | Replace aging primary storage arrays before end-of-support deadline (within 18 months) | functional | Replacement and migration of existing storage | None stated | src_crm_opp_acme_001 (crm_opportunity) |
| REQ-5 | Centralised management to reduce operational burden on a small IT team | functional | Centralised management | None stated | src_crm_opp_acme_001 (crm_opportunity) |
| REQ-7 | Regulatory compliance obligations under HIPAA for data protection and audit trails | functional | Compliance and audit trails | HIPAA | src_crm_acme_001 (account_challenge) |
| REQ-2 | High availability with no single point of failure for clinical systems | technical | High availability | single point of failure | src_crm_opp_acme_001 (crm_opportunity) |
| REQ-3 | Disaster recovery with recovery time objective under four hours | technical | Disaster recovery | four hours | src_crm_opp_acme_001 (crm_opportunity) |
| REQ-4 | Encryption at rest for patient data (HIPAA compliance) | technical | Encryption at rest | HIPAA | src_crm_opp_acme_001 (crm_opportunity) |
| REQ-6 | Increasing storage capacity demands from medical imaging workloads | technical | Capacity and scalability | None stated | src_crm_acme_001 (account_challenge) |

**Business priorities (from CRM)**
- Centralised management to reduce operational burden on a small IT team (src_crm_opp_acme_001)

**Constraints (from CRM)**
- Aging on-premises storage arrays approaching end of support within 18 months (src_crm_acme_001)
- Limited internal storage expertise following recent staff turnover (src_crm_acme_001)
- Confirmed end-of-support concern and HA requirement. (src_crm_opp_acme_001)
- Director of Infrastructure confirmed storage arrays reach end of support in Q2 2027. (src_crm_opp_acme_001)
- Budget discussion deferred — Director said CIO approval is needed for capital spend above a threshold they did not specify. (src_crm_opp_acme_001)

**Unknown requirements (from CRM)**
- budget
- decision maker
- usable capacity
- Annual IT budget and capital expenditure approval process
- Total usable storage capacity currently deployed
- Identity of the economic buyer and decision-making process
- Whether a formal RFP process is required

## 2. Side-by-side comparison

| Requirement | IBM FlashSystem 7300 | IBM Spectrum Virtualize | IBM FlashSystem 5200 | IBM Cloud Object Storage |
|---|---|---|---|---|
| REQ-1: Replace aging primary storage arrays before end-of-support deadline (within 18 months) | Unknown | Partial | Unknown | Unknown |
| REQ-2: High availability with no single point of failure for clinical systems | Partial | Partial | Supported | Unknown |
| REQ-3: Disaster recovery with recovery time objective under four hours | Partial | Partial | Partial | Unknown |
| REQ-4: Encryption at rest for patient data (HIPAA compliance) | Partial | Unknown | Partial | Partial |
| REQ-5: Centralised management to reduce operational burden on a small IT team | Partial | Partial | Unknown | Unknown |
| REQ-6: Increasing storage capacity demands from medical imaging workloads | Unknown | Unknown | Unknown | Partial |
| REQ-7: Regulatory compliance obligations under HIPAA for data protection and audit trails | Unknown | Unknown | Unknown | Unknown |

## 3. Detailed comparison matrix

| Req | Candidate | Fit | Documented capability | Evidence source | Missing information | Limitations to validate |
|---|---|---|---|---|---|---|
| REQ-1 | IBM FlashSystem 7300 | Unknown | None documented | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-1 | IBM Spectrum Virtualize | Partial | Virtualisation of third-party storage arrays into a unified pool; Non-disruptive data migration between storage systems | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | The catalog documents data migration, not replacement scope, hardware support status or cutover timelines.; Compatibility of existing third-party storage with Spectrum Virtualize; Network bandwidth for replication and migration | Virtualising third-party arrays requires a compatibility check against the IBM Interoperability Matrix; Non-disruptive migration timelines depend on data volume and I/O load |
| REQ-1 | IBM FlashSystem 5200 | Unknown | None documented | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | No documented capability for this area in the catalog entry.; Compatibility with existing host bus adapters and switches | None listed |
| REQ-1 | IBM Cloud Object Storage | Unknown | None documented | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | No documented capability for this area in the catalog entry.; Catalog limitation may exclude this area (needs specialist review): 'Object storage is optimised for large, infrequently-modified objects — not a replacement for block storage in transactional workloads' | Object storage is optimised for large, infrequently-modified objects — not a replacement for block storage in transactional workloads |
| REQ-2 | IBM FlashSystem 7300 | Partial | IBM HyperSwap for active-active high availability across two sites | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | Target 'single point of failure' is not documented in the catalog evidence. | None listed |
| REQ-2 | IBM Spectrum Virtualize | Partial | IBM HyperSwap for active-active HA across two sites | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | Target 'single point of failure' is not documented in the catalog evidence. | Replication performance depends on inter-site bandwidth and latency |
| REQ-2 | IBM FlashSystem 5200 | Supported | High availability with no single point of failure; IBM HyperSwap for transparent failover between sites | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | Network topology for replication | HyperSwap requires two storage systems at separate sites — validate site topology with a specialist |
| REQ-2 | IBM Cloud Object Storage | Unknown | None documented | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-3 | IBM FlashSystem 7300 | Partial | IBM Safeguarded Copy for immutable, air-gapped backup snapshots | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | Target 'four hours' is not documented in the catalog evidence.; Workload IOPS and latency requirements; Safeguarded Copy retention schedule and recovery runbook | Safeguarded Copy schedules must be planned; recovery from immutable copies requires a tested runbook |
| REQ-3 | IBM Spectrum Virtualize | Partial | Synchronous and asynchronous replication for disaster recovery; IBM Safeguarded Copy for immutable point-in-time recovery | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | Target 'four hours' is not documented in the catalog evidence.; Network bandwidth for replication and migration | Replication performance depends on inter-site bandwidth and latency |
| REQ-3 | IBM FlashSystem 5200 | Partial | Replication to on-premises or IBM Cloud for disaster recovery | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | Target 'four hours' is not documented in the catalog evidence.; Network topology for replication | Replication bandwidth requirements must be assessed for the customer's network |
| REQ-3 | IBM Cloud Object Storage | Unknown | None documented | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-4 | IBM FlashSystem 7300 | Partial | Encryption at rest with FIPS 140-2 validated drives | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | Target 'HIPAA' is not documented in the catalog evidence. | None listed |
| REQ-4 | IBM Spectrum Virtualize | Unknown | None documented | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-4 | IBM FlashSystem 5200 | Partial | Encryption at rest using FIPS 140-2 validated drives | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | Target 'HIPAA' is not documented in the catalog evidence. | None listed |
| REQ-4 | IBM Cloud Object Storage | Partial | Data encryption in transit (TLS) and at rest | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | Target 'HIPAA' is not documented in the catalog evidence. | None listed |
| REQ-5 | IBM FlashSystem 7300 | Partial | IBM Spectrum Virtualize for unified management across heterogeneous storage | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | The outcome 'reduce' is not documented; the catalog describes capabilities, not results. | None listed |
| REQ-5 | IBM Spectrum Virtualize | Partial | Virtualisation of third-party storage arrays into a unified pool; Consistent management interface across IBM FlashSystem family | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | The outcome 'reduce' is not documented; the catalog describes capabilities, not results. | None listed |
| REQ-5 | IBM FlashSystem 5200 | Unknown | None documented | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | No documented capability for this area in the catalog entry. | HyperSwap requires two storage systems at separate sites — validate site topology with a specialist |
| REQ-5 | IBM Cloud Object Storage | Unknown | None documented | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-6 | IBM FlashSystem 7300 | Unknown | None documented | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-6 | IBM Spectrum Virtualize | Unknown | None documented | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-6 | IBM FlashSystem 5200 | Unknown | None documented | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | No documented capability for this area in the catalog entry.; Workload sizing and performance requirements | Maximum raw capacity scales with enclosure count — sizing must be confirmed for specific workloads |
| REQ-6 | IBM Cloud Object Storage | Partial | Petabyte-scale storage for unstructured and backup data | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | The requirement has no quantified target, so sizing cannot be compared. | None listed |
| REQ-7 | IBM FlashSystem 7300 | Unknown | None documented | src_prod_flashsystem7300_001, https://www.ibm.com/products/flashsystem-7300, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-7 | IBM Spectrum Virtualize | Unknown | None documented | src_prod_specvirt_001, https://www.ibm.com/products/spectrum-virtualize, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-7 | IBM FlashSystem 5200 | Unknown | None documented | src_prod_flashsystem5200_001, https://www.ibm.com/products/flashsystem-5200, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |
| REQ-7 | IBM Cloud Object Storage | Unknown | None documented | src_prod_cos_001, https://www.ibm.com/products/cloud-object-storage, verified 2026-10-01 | No documented capability for this area in the catalog entry. | None listed |

## 4. Strengths and limitations by candidate

### IBM FlashSystem 7300 (src_prod_flashsystem7300_001)
Supported 0, Partial 4, Not supported 0, Unknown 3.

Documented strengths:
- REQ-2 (Partial): IBM HyperSwap for active-active high availability across two sites
- REQ-3 (Partial): IBM Safeguarded Copy for immutable, air-gapped backup snapshots
- REQ-4 (Partial): Encryption at rest with FIPS 140-2 validated drives
- REQ-5 (Partial): IBM Spectrum Virtualize for unified management across heterogeneous storage

Catalog limitations:
- Higher performance tier — validate whether workload requirements justify the additional capability
- Safeguarded Copy schedules must be planned; recovery from immutable copies requires a tested runbook
- AI-driven compression effectiveness depends on data type — validate with a proof of concept for specific workloads

### IBM Spectrum Virtualize (src_prod_specvirt_001)
Supported 0, Partial 4, Not supported 0, Unknown 3.

Documented strengths:
- REQ-1 (Partial): Virtualisation of third-party storage arrays into a unified pool; Non-disruptive data migration between storage systems
- REQ-2 (Partial): IBM HyperSwap for active-active HA across two sites
- REQ-3 (Partial): Synchronous and asynchronous replication for disaster recovery; IBM Safeguarded Copy for immutable point-in-time recovery
- REQ-5 (Partial): Virtualisation of third-party storage arrays into a unified pool; Consistent management interface across IBM FlashSystem family

Catalog limitations:
- Virtualising third-party arrays requires a compatibility check against the IBM Interoperability Matrix
- Replication performance depends on inter-site bandwidth and latency
- Non-disruptive migration timelines depend on data volume and I/O load

### IBM FlashSystem 5200 (src_prod_flashsystem5200_001)
Supported 1, Partial 2, Not supported 0, Unknown 4.

Documented strengths:
- REQ-2 (Supported): High availability with no single point of failure; IBM HyperSwap for transparent failover between sites
- REQ-3 (Partial): Replication to on-premises or IBM Cloud for disaster recovery
- REQ-4 (Partial): Encryption at rest using FIPS 140-2 validated drives

Catalog limitations:
- HyperSwap requires two storage systems at separate sites — validate site topology with a specialist
- Maximum raw capacity scales with enclosure count — sizing must be confirmed for specific workloads
- Replication bandwidth requirements must be assessed for the customer's network

### IBM Cloud Object Storage (src_prod_cos_001)
Supported 0, Partial 2, Not supported 0, Unknown 5.

Documented strengths:
- REQ-4 (Partial): Data encryption in transit (TLS) and at rest
- REQ-6 (Partial): Petabyte-scale storage for unstructured and backup data

Catalog limitations:
- Object storage is optimised for large, infrequently-modified objects — not a replacement for block storage in transactional workloads
- Erasure coding schemes must be selected based on durability and space efficiency trade-offs
- On-premises deployment requires physical hardware planning

## 5. Requirements not yet validated

| Req | Requirement | Best result | Why |
|---|---|---|---|
| REQ-1 | Replace aging primary storage arrays before end-of-support deadline (within 18 months) | Partial | No documented capability for this area in the catalog entry.; The catalog documents data migration, not replacement scope, hardware support status or cutover timelines.; Compatibility of existing third-party storage with Spectrum Virtualize; Network bandwidth for replication and migration; Compatibility with existing host bus adapters and switches; Catalog limitation may exclude this area (needs specialist review): 'Object storage is optimised for large, infrequently-modified objects — not a replacement for block storage in transactional workloads' |
| REQ-3 | Disaster recovery with recovery time objective under four hours | Partial | Target 'four hours' is not documented in the catalog evidence.; Workload IOPS and latency requirements; Safeguarded Copy retention schedule and recovery runbook; Network bandwidth for replication and migration; Network topology for replication; No documented capability for this area in the catalog entry. **Other catalog products with documented evidence (not in this comparison):** IBM Spectrum Protect (Tivoli Storage Manager) (src_prod_specprotect_001): Replication to an off-site Spectrum Protect server for disaster recovery |
| REQ-4 | Encryption at rest for patient data (HIPAA compliance) | Partial | Target 'HIPAA' is not documented in the catalog evidence.; No documented capability for this area in the catalog entry. |
| REQ-5 | Centralised management to reduce operational burden on a small IT team | Partial | The outcome 'reduce' is not documented; the catalog describes capabilities, not results.; No documented capability for this area in the catalog entry. **Other catalog products with documented evidence (not in this comparison):** IBM Guardium Data Protection (src_prod_guardium_001): Integration with SIEM platforms for centralised security operations |
| REQ-6 | Increasing storage capacity demands from medical imaging workloads | Partial | No documented capability for this area in the catalog entry.; Workload sizing and performance requirements; The requirement has no quantified target, so sizing cannot be compared. |
| REQ-7 | Regulatory compliance obligations under HIPAA for data protection and audit trails | Unknown | No documented capability for this area in the catalog entry. **Other catalog products with documented evidence (not in this comparison):** IBM Guardium Data Protection (src_prod_guardium_001): Tamper-proof audit trails for compliance (HIPAA, PCI-DSS, GDPR); IBM Spectrum Protect (Tivoli Storage Manager) (src_prod_specprotect_001): Reporting and compliance dashboards for backup coverage |

## 6. Recommended discovery questions

1. What make, model and age are the arrays being replaced, and which hosts, adapters and switches attach to them?
2. What cutover window and tolerance for migration disruption apply to each clinical or business system?
3. What recovery time and recovery point objectives apply to each workload tier?
4. Where is the recovery site, and what inter-site bandwidth and latency are available?
5. How often is disaster recovery tested today, and what happened in the last test?
6. Is 'four hours' a firm customer target? If so, ask a product specialist to confirm it against product documentation.
7. Which encryption standard and key-management approach does the customer require?
8. Which compliance framework must the encryption support evidence for, and who owns that evidence?
9. Is 'HIPAA' a firm customer target? If so, ask a product specialist to confirm it against product documentation.
10. Who will administer the platform day to day, and which management tools do they use today?
11. Which existing arrays or platforms must be managed from the same interface?
12. What is the current usable capacity and expected growth over the next three to five years?
13. What are the data types and access patterns of the largest consumers (for example imaging)?
14. Which regulations or frameworks apply, and what evidence must be produced for auditors?
15. Which data sources and systems are in scope for audit and monitoring?
16. Can the customer provide: budget?
17. Can the customer provide: decision maker?
18. Can the customer provide: usable capacity?
19. Can the customer provide: Annual IT budget and capital expenditure approval process?
20. Can the customer provide: Total usable storage capacity currently deployed?
21. Can the customer provide: Identity of the economic buyer and decision-making process?
22. Can the customer provide: Whether a formal RFP process is required?
23. Validate with a specialist (IBM FlashSystem 7300): Workload IOPS and latency requirements
24. Validate with a specialist (IBM FlashSystem 7300): Ransomware detection sensitivity tuning for specific data patterns
25. Validate with a specialist (IBM FlashSystem 7300): Safeguarded Copy retention schedule and recovery runbook
26. Validate with a specialist (IBM Spectrum Virtualize): Compatibility of existing third-party storage with Spectrum Virtualize
27. Validate with a specialist (IBM Spectrum Virtualize): Network bandwidth for replication and migration
28. Validate with a specialist (IBM Spectrum Virtualize): Licensing model for specific features
29. Validate with a specialist (IBM FlashSystem 5200): Workload sizing and performance requirements
30. Validate with a specialist (IBM FlashSystem 5200): Network topology for replication
31. Validate with a specialist (IBM FlashSystem 5200): Compatibility with existing host bus adapters and switches
32. Validate with a specialist (IBM Cloud Object Storage): Data type and access patterns — confirm object storage is appropriate for the workload
33. Validate with a specialist (IBM Cloud Object Storage): Durability and erasure coding scheme selection
34. Validate with a specialist (IBM Cloud Object Storage): Network throughput for ingest and retrieval

## 7. Preliminary solution direction

*Preliminary - worth exploring, not a recommendation or validated fit*

- **IBM FlashSystem 5200**: 1 requirement(s) Supported and 2 Partially supported by verified catalog evidence.
- **IBM FlashSystem 7300**: 0 requirement(s) Supported and 4 Partially supported by verified catalog evidence.
- **IBM Spectrum Virtualize**: 0 requirement(s) Supported and 4 Partially supported by verified catalog evidence.
- **IBM Cloud Object Storage**: 0 requirement(s) Supported and 2 Partially supported by verified catalog evidence.

Caveats:
- Preliminary and based only on catalog text; not a validated configuration, sizing or quote.
- No pricing, guaranteed recovery times, performance benchmarks or competitive claims are provided.
- Absence of documentation is shown as Unknown, not as lack of support.
- Every Supported or Partially supported result still needs specialist validation of sizing, topology and compatibility.

---
Seller checklist: confirm customer facts, validate every Supported/Partial result with a specialist, and do not quote pricing, recovery times, performance figures or competitor comparisons from this document.
