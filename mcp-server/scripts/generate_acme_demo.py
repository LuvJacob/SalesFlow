"""Generate the Acme Healthcare demonstration document.

Run (from mcp-server/):  uv run python scripts/generate_acme_demo.py

Writes:  outputs/discovery_brief_acme_healthcare_<timestamp>.docx
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from salesflow_mcp.brief_schema import (
    AccountSummary,
    AgendaItem,
    NextStep,
    OpportunitySummary,
    ProductEntry,
    QualificationGap,
    SalesBriefInput,
    SourceRef,
    SpinQuestion,
    SolutionPositioning,
)
from salesflow_mcp.docx_generator import build_document, resolve_output_path


def main() -> None:
    brief = SalesBriefInput(
        account=AccountSummary(
            account_id="acct_acme_healthcare",
            name="Acme Healthcare",
            industry="Healthcare",
            overview="Fictional regional healthcare network with hospitals and outpatient clinics.",
            challenges=[
                "Aging on-premises storage arrays approaching end of support",
                "Need for high availability for clinical systems",
            ],
            unknowns=["annual IT budget", "total usable storage capacity"],
            synthetic=True,
            source_id="src_crm_acme_001",
        ),
        opportunity=OpportunitySummary(
            opportunity_id="opp_acme_storage_01",
            name="Acme Healthcare storage modernization",
            stage="Discovery",
            requirements=["Replace aging storage", "High availability", "Disaster recovery"],
            stakeholders=[{"role": "Director of Infrastructure", "name": "Synthetic Contact A"}],
            notes=["Initial inquiry received; no prior discovery meeting held."],
            unknowns=["budget", "decision maker", "usable capacity"],
            synthetic=True,
            source_id="src_crm_opp_acme_001",
        ),
        spin_questions=[
            SpinQuestion(category="Situation",
                         question="Can you walk me through your current storage environment — what platforms are in production and when were they originally deployed?"),
            SpinQuestion(category="Situation",
                         question="How many sites — hospitals, outpatient clinics — rely on shared storage today, and how is replication or DR currently handled between them?"),
            SpinQuestion(category="Problem",
                         question="Your arrays are approaching end of support — what specific risks does that create for your team right now? Are you seeing performance degradation or support gaps?"),
            SpinQuestion(category="Problem",
                         question="What happens to clinical workflows — EHR access, imaging, lab systems — if your primary storage has an unplanned outage?"),
            SpinQuestion(category="Implication",
                         question="If an end-of-support event caused a compliance gap or an audit finding, what would the downstream impact look like for your organisation?"),
            SpinQuestion(category="Implication",
                         question="What is the estimated cost — operational, clinical, or reputational — of even a two-hour storage outage during peak clinical hours?"),
            SpinQuestion(category="Need-Payoff",
                         question="If you had a modernised storage platform that guaranteed sub-minute RTO for your clinical systems and was fully supported, how would that change your team's day-to-day risk posture?"),
            SpinQuestion(category="Need-Payoff",
                         question="Beyond storage replacement, if you could solve the DR gap at the same time, what would that unlock for your infrastructure roadmap over the next 18–24 months?"),
        ],
        agenda=[
            AgendaItem(time_slot="0–3 min",   segment="Introductions & agenda alignment",
                       goal="Confirm attendees, set expectations, get agreement on outcome"),
            AgendaItem(time_slot="3–8 min",   segment="Situation questions",
                       goal="Map current environment, sites, and storage topology"),
            AgendaItem(time_slot="8–15 min",  segment="Problem questions",
                       goal="Uncover active pain around end-of-support and HA gaps"),
            AgendaItem(time_slot="15–20 min", segment="Implication questions",
                       goal="Quantify risk and business impact"),
            AgendaItem(time_slot="20–25 min", segment="Need-Payoff questions",
                       goal="Build shared vision of desired outcome"),
            AgendaItem(time_slot="25–28 min", segment="Preliminary solution positioning",
                       goal="Share directional capabilities; avoid over-specifying"),
            AgendaItem(time_slot="28–30 min", segment="Next steps",
                       goal="Agree on follow-up: technical deep-dive, RFI, or assessment"),
        ],
        solution_positioning=SolutionPositioning(
            products=[
                ProductEntry(
                    product_id="prod_storage_01",
                    name="Example Enterprise Storage Platform (synthetic)",
                    summary="Placeholder entry for a block storage platform aimed at high availability.",
                    capabilities=[
                        "High availability (placeholder)",
                        "Disaster recovery support (placeholder)",
                    ],
                    limitations=[
                        "Unverified — do not present as a real product capability",
                        "No pricing or performance specifications available",
                    ],
                    verification_status="synthetic_unverified",
                    source_id="src_prod_synthetic_001",
                    synthetic=True,
                ),
            ],
            directional_angle=(
                "We have storage platforms purpose-built for organisations that need "
                "always-on availability for mission-critical clinical systems, with "
                "integrated DR that can simplify your multi-site architecture — we would "
                "like to understand your environment better before recommending a "
                "specific configuration."
            ),
            notice=(
                "Entries marked synthetic_unverified are placeholders without a verified "
                "source_url/verified_date. Do not present them as real product facts."
            ),
        ),
        qualification_gaps=[
            QualificationGap(gap="Annual IT budget",
                             why_it_matters="Cannot size or qualify the opportunity"),
            QualificationGap(gap="Total usable storage capacity",
                             why_it_matters="Cannot scope a replacement solution"),
            QualificationGap(gap="Decision-maker identity",
                             why_it_matters="Director of Infrastructure may not be the economic buyer"),
            QualificationGap(gap="RTO / RPO targets",
                             why_it_matters="HA and DR requirements cannot be scoped without recovery objectives"),
            QualificationGap(gap="Regulatory / compliance constraints",
                             why_it_matters="Healthcare environments (HIPAA, etc.) may drive architecture requirements"),
            QualificationGap(gap="Current storage vendors / platforms",
                             why_it_matters="Needed to assess migration complexity"),
            QualificationGap(gap="Timeline and trigger event",
                             why_it_matters="Is end-of-support a hard deadline? What is the contract expiry date?"),
            QualificationGap(gap="Multi-site DR topology",
                             why_it_matters="Number of sites, network connectivity, and replication requirements unknown"),
        ],
        next_steps=[
            NextStep(action="Schedule a 90-minute technical deep-dive to map the current storage topology and performance baselines"),
            NextStep(action="Request the IT budget envelope or approval process from the Director of Infrastructure"),
            NextStep(action="Confirm the economic decision-maker and procurement stakeholders"),
            NextStep(action="Obtain current storage capacity, IOPS, and latency metrics"),
            NextStep(action="Identify any contractual end-of-support deadlines for existing arrays"),
            NextStep(action="Send a follow-up summary with directional solution positioning — for seller review before sending"),
        ],
        sources=[
            SourceRef(source_id="src_crm_acme_001"),
            SourceRef(source_id="src_crm_opp_acme_001"),
            SourceRef(source_id="src_prod_synthetic_001"),
        ],
        playbook_available=False,
        methodology_note=(
            "SPIN playbook returned not_found from the MCP server (data/playbooks/ fixture "
            "pending from Lane C). Questions are structured using standard SPIN Selling "
            "methodology applied to the retrieved account and opportunity context."
        ),
    )

    dest = resolve_output_path(brief.account.name)
    written = build_document(brief, dest)
    print(f"Document saved: {written}")
    print(f"Size: {written.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
