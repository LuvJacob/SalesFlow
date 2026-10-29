"""Word document generator for SalesFlow discovery meeting briefs.

Produces a professionally formatted .docx file from a validated SalesBriefInput.
Uses python-docx (https://python-docx.readthedocs.io/).

Rules (inherited from project-wide security and grounding rules):
- This module formats supplied content only. It never invents customer facts,
  product capabilities, prices, or competitor claims.
- Synthetic / unverified content is explicitly labelled in the document.
- Output is written to the resolved outputs/ directory only.
- No directory traversal: filenames are sanitised; absolute paths are rejected.
- Files are never silently overwritten.
- No stdout writes: the module logs to stderr.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor
from .brief_schema import (
    AgendaItem,
    ProductEntry,
    QualificationGap,
    SalesBriefInput,
    SpinQuestion,
)

log = logging.getLogger("salesflow.docx")

# ---------------------------------------------------------------------------
# Brand palette (no IBM logos — generic enterprise professional)
# ---------------------------------------------------------------------------
NAVY = RGBColor(0x1A, 0x3A, 0x6C)       # Deep navy for headings
BLUE_ACCENT = RGBColor(0x1F, 0x5B, 0xAC) # Mid-blue for subheadings
MUTED_GREY = RGBColor(0x57, 0x60, 0x6A)  # Muted text / disclaimers
TABLE_HEADER_BG = "1A3A6C"               # Navy for table header rows (hex, no #)
TABLE_ROW_ALT = "EBF0F8"                 # Light blue-grey for alternating rows
BLACK = RGBColor(0x1F, 0x23, 0x28)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

# ---------------------------------------------------------------------------
# Output directory resolution
# ---------------------------------------------------------------------------

_MAX_FILENAME_LEN = 80
_UNSAFE_CHARS = re.compile(r"[^\w\-. ]")


def _outputs_dir() -> Path:
    """Resolve the outputs/ directory relative to the repository root.

    Override with the SALESFLOW_OUTPUTS_DIR environment variable for tests.
    Never falls back to cwd() — that would be non-deterministic inside Bob.
    """
    override = os.environ.get("SALESFLOW_OUTPUTS_DIR")
    if override:
        p = Path(override)
        if not p.is_absolute():
            raise ValueError("SALESFLOW_OUTPUTS_DIR must be an absolute path.")
        return p
    # src/salesflow_mcp/docx_generator.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3] / "outputs"


def _safe_filename(raw: str) -> str:
    """Return a safe filename (no path separators, no overlong strings)."""
    # Strip any path component the caller might have injected
    name = Path(raw).name
    # Replace unsafe characters with underscores
    name = _UNSAFE_CHARS.sub("_", name)
    # Collapse multiple underscores/spaces
    name = re.sub(r"[_ ]{2,}", "_", name).strip("_. ")
    if not name:
        name = "brief"
    if len(name) > _MAX_FILENAME_LEN:
        name = name[:_MAX_FILENAME_LEN]
    return name


def resolve_output_path(account_name: str, outputs_dir: Optional[Path] = None) -> Path:
    """Return a unique, safe output path for the brief document.

    Raises FileExistsError if the computed path already exists.
    Raises ValueError for unsafe inputs.
    """
    base_dir = outputs_dir if outputs_dir is not None else _outputs_dir()
    base_dir.mkdir(parents=True, exist_ok=True)

    slug = _safe_filename(account_name.lower().replace(" ", "_"))
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"discovery_brief_{slug}_{timestamp}.docx"
    dest = base_dir / filename

    # Guard against path traversal: resolved path must be inside base_dir
    try:
        dest.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(f"Computed output path escapes the outputs directory: {dest}")

    if dest.exists():
        raise FileExistsError(f"Output file already exists: {dest}")

    return dest


# ---------------------------------------------------------------------------
# Helpers for python-docx styling
# ---------------------------------------------------------------------------


def _set_cell_bg(cell, hex_color: str) -> None:
    """Set a table cell's background fill colour (OOXML shading element)."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _add_run(para, text: str, bold: bool = False, italic: bool = False,
             color: Optional[RGBColor] = None, size_pt: Optional[int] = None) -> None:
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color
    if size_pt:
        run.font.size = Pt(size_pt)


def _heading(doc: Document, text: str, level: int = 1) -> None:
    """Add a styled section heading without relying on built-in Heading styles
    (which may be unavailable in minimal docx templates)."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(14 if level == 1 else 8)
    para.paragraph_format.space_after = Pt(4)
    run = para.add_run(text.upper() if level == 1 else text)
    run.bold = True
    run.font.size = Pt(13 if level == 1 else 11)
    run.font.color.rgb = NAVY if level == 1 else BLUE_ACCENT
    # Bottom border on H1
    if level == 1:
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "1A3A6C")
        pBdr.append(bottom)
        pPr.append(pBdr)


def _disclaimer(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(2)
    run = para.add_run(f"⚠ {text}")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED_GREY


def _two_col_table(doc: Document, rows: list[tuple[str, str]],
                   col_widths: tuple[float, float] = (2.2, 4.0)) -> None:
    """Render a simple two-column key/value table."""
    tbl = doc.add_table(rows=len(rows), cols=2)
    tbl.style = "Table Grid"
    for i, (key, val) in enumerate(rows):
        row = tbl.rows[i]
        row.cells[0].width = Inches(col_widths[0])
        row.cells[1].width = Inches(col_widths[1])
        p0 = row.cells[0].paragraphs[0]
        _add_run(p0, key, bold=True, size_pt=10)
        p1 = row.cells[1].paragraphs[0]
        _add_run(p1, val, size_pt=10)
        bg = TABLE_ROW_ALT if i % 2 == 0 else "FFFFFF"
        _set_cell_bg(row.cells[0], bg)
        _set_cell_bg(row.cells[1], bg)
    doc.add_paragraph()  # spacing


def _header_table(doc: Document, headers: list[str],
                  rows: list[list[str]], col_widths: Optional[list[float]] = None) -> None:
    """Render a multi-column table with a navy header row."""
    n_cols = len(headers)
    tbl = doc.add_table(rows=1 + len(rows), cols=n_cols)
    tbl.style = "Table Grid"
    # Header row
    hdr_row = tbl.rows[0]
    for j, h in enumerate(headers):
        cell = hdr_row.cells[j]
        if col_widths:
            cell.width = Inches(col_widths[j])
        _set_cell_bg(cell, TABLE_HEADER_BG)
        p = cell.paragraphs[0]
        _add_run(p, h, bold=True, color=WHITE, size_pt=10)
    # Data rows
    for i, data_row in enumerate(rows):
        tr = tbl.rows[i + 1]
        bg = TABLE_ROW_ALT if i % 2 == 0 else "FFFFFF"
        for j, cell_text in enumerate(data_row):
            cell = tr.cells[j]
            if col_widths:
                cell.width = Inches(col_widths[j])
            _set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            _add_run(p, str(cell_text), size_pt=10)
    doc.add_paragraph()


def _bullet_list(doc: Document, items: list[str], italic: bool = False) -> None:
    for item in items:
        para = doc.add_paragraph(style="List Bullet")
        run = para.add_run(item)
        run.font.size = Pt(10)
        run.italic = italic


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_cover(doc: Document, brief: SalesBriefInput) -> None:
    doc.add_paragraph()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(title, "DISCOVERY MEETING BRIEF", bold=True, color=NAVY, size_pt=22)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(subtitle, brief.account.name, bold=True, color=BLUE_ACCENT, size_pt=16)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ts = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    _add_run(meta, f"Prepared: {ts}  |  Stage: {brief.opportunity.stage or 'Discovery'}",
             color=MUTED_GREY, size_pt=10)

    if brief.account.synthetic or brief.opportunity.synthetic:
        warn = doc.add_paragraph()
        warn.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(warn,
                 "This document contains synthetic/fictional data for demonstration purposes only.",
                 italic=True, color=MUTED_GREY, size_pt=9)
    doc.add_paragraph()


def _build_account(doc: Document, brief: SalesBriefInput) -> None:
    _heading(doc, "1. Account Snapshot")
    acct = brief.account
    rows = [
        ("Account ID", acct.account_id),
        ("Company", acct.name),
        ("Industry", acct.industry or "—"),
        ("Overview", acct.overview or "—"),
        ("Data Status", "⚠ Synthetic / unverified" if acct.synthetic else "Verified"),
        ("Source", acct.source_id or "—"),
    ]
    _two_col_table(doc, rows)

    if acct.challenges:
        _heading(doc, "Known Challenges", level=2)
        _bullet_list(doc, acct.challenges)

    if acct.unknowns:
        _heading(doc, "Open Unknowns (from CRM)", level=2)
        _bullet_list(doc, [f"Unknown: {u}" for u in acct.unknowns], italic=True)


def _build_opportunity(doc: Document, brief: SalesBriefInput) -> None:
    _heading(doc, "2. Opportunity Overview")
    opp = brief.opportunity
    rows = [
        ("Opportunity ID", opp.opportunity_id),
        ("Name", opp.name or "—"),
        ("Stage", opp.stage or "—"),
        ("Data Status", "⚠ Synthetic / unverified" if opp.synthetic else "Verified"),
        ("Source", opp.source_id or "—"),
    ]
    _two_col_table(doc, rows)

    if opp.requirements:
        _heading(doc, "Stated Requirements", level=2)
        _bullet_list(doc, opp.requirements)

    if opp.stakeholders:
        _heading(doc, "Stakeholders", level=2)
        stk_rows = []
        for s in opp.stakeholders:
            role = str(s.get("role", "—"))
            name = str(s.get("name", "—"))
            stk_rows.append([role, name])
        _header_table(doc, ["Role", "Name"], stk_rows, col_widths=[2.8, 3.4])

    if opp.notes:
        _heading(doc, "Meeting History / Notes", level=2)
        _bullet_list(doc, opp.notes)

    if opp.unknowns:
        _heading(doc, "Open Qualification Gaps (from Opportunity)", level=2)
        _bullet_list(doc, [f"Unknown: {u}" for u in opp.unknowns], italic=True)


def _build_spin(doc: Document, questions: list[SpinQuestion],
                playbook_available: bool, methodology_note: Optional[str]) -> None:
    _heading(doc, "3. SPIN Discovery Questions")

    if not playbook_available:
        _disclaimer(doc, "SPIN playbook was not available from the MCP server. "
                         "Questions below are structured using standard SPIN methodology "
                         "applied to retrieved account and opportunity data.")
    if methodology_note:
        _disclaimer(doc, methodology_note)

    # Group by category in SPIN order
    order = ["Situation", "Problem", "Implication", "Need-Payoff"]
    grouped: dict[str, list[str]] = {c: [] for c in order}
    for q in questions:
        if q.category in grouped:
            grouped[q.category].append(q.question)

    for cat in order:
        qs = grouped[cat]
        if not qs:
            continue
        _heading(doc, cat, level=2)
        for i, q in enumerate(qs, 1):
            para = doc.add_paragraph(style="List Number")
            run = para.add_run(q)
            run.font.size = Pt(10)


def _build_agenda(doc: Document, agenda: list[AgendaItem]) -> None:
    _heading(doc, "4. 30-Minute Meeting Agenda")
    if not agenda:
        doc.add_paragraph("No agenda provided.").runs[0].font.color.rgb = MUTED_GREY
        return
    rows = [[a.time_slot, a.segment, a.goal] for a in agenda]
    _header_table(doc, ["Time", "Segment", "Goal"], rows,
                  col_widths=[1.0, 2.0, 3.2])


def _build_gaps(doc: Document, gaps: list[QualificationGap]) -> None:
    _heading(doc, "5. Missing Requirements / Qualification Gaps")
    if not gaps:
        doc.add_paragraph("No gaps recorded.").runs[0].font.color.rgb = MUTED_GREY
        return
    rows = [[g.gap, g.why_it_matters] for g in gaps]
    _header_table(doc, ["Gap", "Why It Matters"], rows, col_widths=[2.8, 3.4])


def _build_solution(doc: Document, positioning: Optional[object]) -> None:
    _heading(doc, "6. Preliminary Solution Positioning")
    if positioning is None or not positioning.products:  # type: ignore[union-attr]
        para = doc.add_paragraph()
        _add_run(para, "No product matches retrieved. Run search_product_knowledge "
                       "and retry.", italic=True, color=MUTED_GREY, size_pt=10)
        return

    _disclaimer(doc,
        "All product entries below are marked by their verification status. "
        "Entries labelled synthetic_unverified are placeholders only — do not "
        "present them to customers as verified product facts or commitments. "
        "No pricing or competitive claims are included.")

    if positioning.directional_angle:  # type: ignore[union-attr]
        _heading(doc, "Positioning Angle", level=2)
        para = doc.add_paragraph()
        _add_run(para, f'"{positioning.directional_angle}"', italic=True, size_pt=10)  # type: ignore[union-attr]

    _heading(doc, "Matched Product Entries", level=2)
    for prod in positioning.products:  # type: ignore[union-attr]
        _heading(doc, prod.name, level=2)
        is_synthetic = prod.verification_status != "verified"
        status_text = "⚠ SYNTHETIC / UNVERIFIED — placeholder only" if is_synthetic else "✓ Verified"
        rows = [
            ("Product ID", prod.product_id),
            ("Verification", status_text),
            ("Summary", prod.summary or "—"),
            ("Source", prod.source_id or "—"),
            ("Source URL", prod.source_url or "—"),
            ("Verified Date", prod.verified_date or "—"),
        ]
        _two_col_table(doc, rows)

        if prod.capabilities:
            _heading(doc, "Capabilities (as listed in catalog)", level=2)
            _bullet_list(doc, prod.capabilities)

        if prod.limitations:
            _heading(doc, "Limitations / Caveats", level=2)
            _bullet_list(doc, prod.limitations, italic=True)

    if positioning.notice:  # type: ignore[union-attr]
        _disclaimer(doc, positioning.notice)


def _build_next_steps(doc: Document, steps: list[object]) -> None:
    _heading(doc, "7. Recommended Next Steps")
    if not steps:
        doc.add_paragraph("No next steps specified.").runs[0].font.color.rgb = MUTED_GREY
        return
    for i, step in enumerate(steps, 1):
        para = doc.add_paragraph(style="List Number")
        _add_run(para, str(getattr(step, "action", step)), size_pt=10)


def _build_sources(doc: Document, brief: SalesBriefInput) -> None:
    _heading(doc, "8. Sources and Disclaimers")

    if brief.sources:
        rows = []
        for s in brief.sources:
            rows.append([
                s.source_id or "—",
                s.source_url or "—",
                s.verified_date or "—",
            ])
        _header_table(doc, ["Source ID", "Source URL", "Verified Date"],
                      rows, col_widths=[2.0, 2.8, 1.4])

    disclaimers = [
        "All customer and account data in this document is synthetic and fictional, "
        "created for demonstration purposes only.",
        "Product catalog entries marked synthetic_unverified are placeholders. "
        "Do not present them as verified IBM product capabilities, guarantees, or pricing.",
        "This document was generated by SalesFlow (IBM Bob hackathon project). "
        "All content must be reviewed by the seller before use in customer-facing communications.",
        "No pricing, discounts, or binding commitments are expressed or implied.",
    ]
    for d in disclaimers:
        _disclaimer(doc, d)

    footer_para = doc.add_paragraph()
    footer_para.paragraph_format.space_before = Pt(12)
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(footer_para, "Generated by SalesFlow · IBM Bob Hackathon",
             color=MUTED_GREY, size_pt=8)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_document(brief: SalesBriefInput, dest: Path) -> Path:
    """Build a .docx discovery brief and write it to *dest*.

    Returns the resolved path of the written file.
    Raises FileExistsError if dest already exists (caller should use
    resolve_output_path() which enforces uniqueness).
    Raises ValueError for schema violations (propagated from Pydantic).
    """
    if dest.exists():
        raise FileExistsError(f"Output file already exists: {dest}")

    doc = Document()

    # Page margins (1 inch all round)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Default paragraph font
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    doc.styles["Normal"].font.color.rgb = BLACK

    _build_cover(doc, brief)
    _build_account(doc, brief)
    doc.add_page_break()
    _build_opportunity(doc, brief)
    _build_spin(doc, brief.spin_questions, brief.playbook_available, brief.methodology_note)
    _build_agenda(doc, brief.agenda)
    _build_gaps(doc, brief.qualification_gaps)
    doc.add_page_break()
    _build_solution(doc, brief.solution_positioning)
    _build_next_steps(doc, brief.next_steps)
    _build_sources(doc, brief)

    doc.save(str(dest))
    log.info("document saved: %s (%d bytes)", dest.name, dest.stat().st_size)
    return dest
