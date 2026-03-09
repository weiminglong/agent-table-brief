from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    file: str
    start_line: int
    end_line: int
    kind: str


class ColumnInfo(BaseModel):
    name: str
    type: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class JoinPath(BaseModel):
    to_table: str
    on: list[tuple[str, str]] = Field(default_factory=list)
    type: str | None = None
    confidence: float = 0.0


class QueryPattern(BaseModel):
    source_model: str
    columns_used: list[str] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)


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
    field_confidence: dict[str, float] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    field_evidence: dict[str, list[EvidenceRef]] = Field(default_factory=dict, exclude=True)
    columns: list[ColumnInfo] = Field(default_factory=list)
    joins: list[JoinPath] = Field(default_factory=list)
    query_patterns: list[QueryPattern] = Field(default_factory=list)
    column_usage: dict[str, int] = Field(default_factory=dict)


class Catalog(BaseModel):
    repo_root: str
    project_type: str
    generated_at: datetime
    version: str
    briefs: list[TableBrief]


class CompareEntry(BaseModel):
    table: str
    brief: TableBrief


class CompareResult(BaseModel):
    tables: list[CompareEntry]
    differences: dict[str, list[str | None]]


class ScanResult(BaseModel):
    repo_key: str
    repo_root: str
    effective_root: str
    project_type: str
    scan_id: int
    status: str
    reused: bool
    brief_count: int
    tables: list[str] = Field(default_factory=list)
    generated_at: datetime


class RepoSummary(BaseModel):
    repo_key: str
    repo_root: str
    effective_root: str
    project_type: str
    brief_count: int
    generated_at: datetime


class MaintenanceResult(BaseModel):
    repos_considered: int
    scans_removed: int


class SearchHit(BaseModel):
    table: str
    rank: float
    brief: TableBrief


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]


class JoinPathStep(BaseModel):
    from_table: str
    to_table: str
    on: list[tuple[str, str]] = Field(default_factory=list)
    join_type: str | None = None
    confidence: float = 0.0


class JoinPathResult(BaseModel):
    from_table: str
    to_table: str
    path: list[JoinPathStep] = Field(default_factory=list)
    found: bool = False


class LineageNode(BaseModel):
    table: str
    depth: int
    direction: str


class LineageResult(BaseModel):
    origin: str
    direction: str
    max_depth: int | None = None
    nodes: list[LineageNode] = Field(default_factory=list)


class CliError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
