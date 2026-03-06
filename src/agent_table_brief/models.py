from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    file: str
    start_line: int
    end_line: int
    kind: str


class TableBrief(BaseModel):
    table: str
    purpose: str | None = None
    grain: str | None = None
    primary_keys: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    filters_or_exclusions: list[str] = Field(default_factory=list)
    freshness_hints: list[str] = Field(default_factory=list)
    downstream_usage: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    confidence: float
    evidence: list[EvidenceRef] = Field(default_factory=list)
    field_evidence: dict[str, list[EvidenceRef]] = Field(default_factory=dict, exclude=True)


class Catalog(BaseModel):
    repo_root: str
    project_type: str
    generated_at: datetime
    version: str
    briefs: list[TableBrief]
