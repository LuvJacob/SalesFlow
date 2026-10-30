"""Generate the sample Acme Healthcare solution comparison (Markdown).

Run (from mcp-server/):  uv run python scripts/generate_acme_comparison.py

Calls the compare_solutions tool function against the repository's data/ and
renders the result to docs/samples/acme_healthcare_solution_comparison.md.
Every statement in the file comes from the tool output; nothing is hand-written
except the table headings.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from salesflow_mcp.server import compare_solutions

OUT = Path(__file__).resolve().parents[2] / "docs" / "samples" / "acme_healthcare_solution_comparison.md"
SHORT = {
    "Supported": "Supported",
    "Partially supported": "Partial",
    "Not supported": "Not supported",
    "Unknown / insufficient evidence": "Unknown",
}


def cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render(r: dict) -> str:
    d = r["data"]
    ov = d["requirements_overview"]
    names = {c["product_id"]: c["name"] for c in d["candidates"]}
    L: list[str] = []

    L += [
        f"# Solution Comparison: Acme Healthcare - {d['opportunity_name']}",
        "",
        "DRAFT - for seller review. Not sent.",
        f"Data status: Retrieved via MCP `compare_solutions` (account `{d['account_id']}`, opportunity `{d['opportunity_id']}`). "
        f"Synthetic customer data: {'yes' if d['synthetic_customer_data'] else 'no'}. "
        f"Illustrative only: {'yes' if d['illustrative'] else 'no (candidates are verified catalog entries)'}.",
        "",
        d["notice"],
        "",
        f"Candidate selection: `{d['candidate_selection']['method']}`.",
        "",
        "## 1. Requirements overview",
        "",
        "| ID | Requirement | Type | Area | Measurable targets | Source |",
        "|---|---|---|---|---|---|",
    ]
    for i in ov["functional"] + ov["technical"] + ov["unmapped"]:
        L.append(
            f"| {i['requirement_id']} | {cell(i['text'])} | {i['type']} | {i['category_label']} | "
            f"{cell(', '.join(i['qualifiers']) or 'None stated')} | {i['source_id']} ({i['source']}) |"
        )
    L += ["", "**Business priorities (from CRM)**"]
    L += [f"- {cell(b['text'])} ({b['source_id']})" for b in ov["business_priorities"]] or ["- None identified"]
    L += ["", "**Constraints (from CRM)**"]
    L += [f"- {cell(c['text'])} ({c['source_id']})" for c in ov["constraints"]] or ["- None identified"]
    L += ["", "**Unknown requirements (from CRM)**"]
    L += [f"- {cell(u['item'])}" for u in ov["unknown_requirements"]] or ["- None recorded"]

    L += ["", "## 2. Side-by-side comparison", ""]
    pids = [c["product_id"] for c in d["candidates"]]
    L.append("| Requirement | " + " | ".join(names[p] for p in pids) + " |")
    L.append("|---|" + "---|" * len(pids))
    for s in d["side_by_side"]:
        L.append(f"| {s['requirement_id']}: {cell(s['requirement'])} | " + " | ".join(SHORT[s["results"][p]] for p in pids) + " |")

    L += [
        "",
        "## 3. Detailed comparison matrix",
        "",
        "| Req | Candidate | Fit | Documented capability | Evidence source | Missing information | Limitations to validate |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in d["comparison_matrix"]:
        src = m["evidence_source"]
        L.append(
            f"| {m['requirement_id']} | {cell(m['product_name'])} | {SHORT[m['fit_status']]} | "
            f"{cell('; '.join(m['documented_capability']) or 'None documented')} | "
            f"{src['source_id']}, {src['source_url']}, verified {src['verified_date']} | "
            f"{cell('; '.join(m['missing_information']) or 'None')} | "
            f"{cell('; '.join(m['limitations']) or 'None listed')} |"
        )

    L += ["", "## 4. Strengths and limitations by candidate"]
    for s in d["product_summaries"]:
        c = s["status_counts"]
        L += [
            "",
            f"### {s['name']} ({s['catalog_source']['source_id']})",
            f"Supported {c['Supported']}, Partial {c['Partially supported']}, "
            f"Not supported {c['Not supported']}, Unknown {c['Unknown / insufficient evidence']}.",
            "",
            "Documented strengths:",
        ]
        L += [f"- {x['requirement_id']} ({SHORT[x['fit_status']]}): {cell('; '.join(x['documented_capability']))}" for x in s["strengths"]] or ["- None documented for these requirements"]
        L += ["", "Catalog limitations:"]
        L += [f"- {cell(x)}" for x in s["limitations"]] or ["- None listed"]
        if s["conflicts"]:
            L += ["", "Conflicting catalog information:"] + [f"- {cell(x['detail'])}" for x in s["conflicts"]]

    L += [
        "",
        "## 5. Requirements not yet validated",
        "",
        "| Req | Requirement | Best result | Why |",
        "|---|---|---|---|",
    ]
    for n in d["requirements_not_yet_validated"]:
        others = "; ".join(
            f"{o['name']} ({o['evidence_source']['source_id']}): {'; '.join(o['documented_capability'])}"
            for o in n["other_catalog_products_with_documented_evidence"]
        )
        why = cell("; ".join(n["reasons"])) + (f" **Other catalog products with documented evidence (not in this comparison):** {cell(others)}" if others else "")
        L.append(f"| {n['requirement_id']} | {cell(n['requirement'])} | {SHORT[n['best_status']]} | {why} |")
    if not d["requirements_not_yet_validated"]:
        L.append("| - | All requirements have a Supported candidate (still needs specialist validation) | - | - |")

    L += ["", "## 6. Recommended discovery questions", ""]
    L += [f"{i}. {cell(q['question'])}" for i, q in enumerate(d["recommended_discovery_questions"], 1)]

    pd = d["preliminary_solution_direction"]
    L += ["", f"## 7. Preliminary solution direction", "", f"*{pd['label']}*", ""]
    L += [f"- **{w['name']}**: {w['rationale']}" for w in pd["worth_exploring"]] or ["- No candidate can be offered as worth exploring on current evidence."]
    L += ["", "Caveats:"] + [f"- {c}" for c in pd["caveats"]]
    L += [
        "",
        "---",
        "Seller checklist: confirm customer facts, validate every Supported/Partial result with a specialist, "
        "and do not quote pricing, recovery times, performance figures or competitor comparisons from this document.",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    r = compare_solutions(account_id="acct_acme_healthcare")
    if r.get("status") != "ok":
        raise SystemExit(f"compare_solutions failed: {r.get('error', {}).get('message')}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(r), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
