"""Pydantic schema for the generate_sales_brief_document MCP tool input.

All fields that originate from MCP tool results should be passed through
unchanged. Fields marked Optional have sensible defaults so callers can omit
sections that were not retrieved (e.g. when a playbook returns not_found).

Rules:
- The schema validates structure; it does not invent or alter content.
- Synthetic / unverified flags are passed through as supplied by the MCP tools.
- No pricing, no competitive claims, no customer PII.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class AccountSummary(BaseModel):
    account_id: str = Field(..., min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    industry: Optional[str] = None
    overview: Optional[str] = None
    challenges: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    synthetic: bool = True
    source_id: Optional[str] = None


class OpportunitySummary(BaseModel):
    opportunity_id: str = Field(..., min_length=1, max_length=200)
    name: Optional[str] = None
    stage: Optional[str] = None
    requirements: list[str] = Field(default_factory=list)
    stakeholders: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    synthetic: bool = True
    source_id: Optional[str] = None


class SpinQuestion(BaseModel):
    category: str = Field(..., description="Situation | Problem | Implication | Need-Payoff")
    question: str = Field(..., min_length=1, max_length=1000)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        allowed = {"Situation", "Problem", "Implication", "Need-Payoff"}
        if v not in allowed:
            raise ValueError(f"category must be one of {sorted(allowed)}")
        return v


class AgendaItem(BaseModel):
    time_slot: str = Field(..., min_length=1, max_length=50, description='e.g. "0–3 min"')
    segment: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=500)


class ProductEntry(BaseModel):
    product_id: str
    name: str
    summary: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    verification_status: str = "synthetic_unverified"
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    verified_date: Optional[str] = None
    synthetic: bool = True


class SolutionPositioning(BaseModel):
    products: list[ProductEntry] = Field(default_factory=list)
    directional_angle: Optional[str] = None
    notice: Optional[str] = None


class QualificationGap(BaseModel):
    gap: str = Field(..., min_length=1, max_length=300)
    why_it_matters: str = Field(..., min_length=1, max_length=500)


class NextStep(BaseModel):
    action: str = Field(..., min_length=1, max_length=500)


class SourceRef(BaseModel):
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    verified_date: Optional[str] = None


class SalesBriefInput(BaseModel):
    """Validated input for generate_sales_brief_document.

    Pass the structured content retrieved from MCP tools directly into the
    matching fields. The generator will format it; it will not add, invent,
    or change the content.
    """

    # Required core sections
    account: AccountSummary
    opportunity: OpportunitySummary

    # Discovery content
    spin_questions: list[SpinQuestion] = Field(default_factory=list)
    agenda: list[AgendaItem] = Field(default_factory=list)

    # Solution fit
    solution_positioning: Optional[SolutionPositioning] = None

    # Qualification and planning
    qualification_gaps: list[QualificationGap] = Field(default_factory=list)
    next_steps: list[NextStep] = Field(default_factory=list)

    # Source references (union of all sources used)
    sources: list[SourceRef] = Field(default_factory=list)

    # Metadata
    playbook_available: bool = False
    playbook_source_id: Optional[str] = None
    methodology_note: Optional[str] = None

    @field_validator("spin_questions")
    @classmethod
    def _spin_limit(cls, v: list[SpinQuestion]) -> list[SpinQuestion]:
        if len(v) > 20:
            raise ValueError("spin_questions must not exceed 20 items.")
        return v

    @field_validator("agenda")
    @classmethod
    def _agenda_limit(cls, v: list[AgendaItem]) -> list[AgendaItem]:
        if len(v) > 30:
            raise ValueError("agenda must not exceed 30 items.")
        return v
