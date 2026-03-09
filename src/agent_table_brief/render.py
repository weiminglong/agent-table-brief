from __future__ import annotations

import json

from agent_table_brief.models import (
    Catalog,
    CompareResult,
    EvidenceRef,
    LineageResult,
    SearchResult,
    TableBrief,
)


def render_brief_json(brief: TableBrief) -> str:
    return brief.model_dump_json(indent=2)


def render_catalog_json(catalog: Catalog) -> str:
    return catalog.model_dump_json(indent=2)


def render_brief_markdown(brief: TableBrief) -> str:
    lines = [f"# {brief.table}", ""]
    lines.extend(_render_field("Purpose", brief.purpose))
    lines.extend(_render_field("Grain", brief.grain))
    lines.extend(_render_field("Primary Keys", ", ".join(brief.primary_keys)))
    lines.extend(_render_field("Derived From", ", ".join(brief.derived_from)))
    lines.extend(_render_field("Filters / Exclusions", ", ".join(brief.filters_or_exclusions)))
    lines.extend(_render_field("Freshness Hints", ", ".join(brief.freshness_hints)))
    lines.extend(_render_field("Downstream Usage", ", ".join(brief.downstream_usage)))
    lines.extend(_render_field("Alternatives", ", ".join(brief.alternatives)))
    lines.extend(_render_field("Confidence", f"{brief.confidence:.2f}"))
    if brief.columns:
        lines.append("## Columns")
        for col in brief.columns:
            desc = f" — {col.description}" if col.description else ""
            type_str = f" ({col.type})" if col.type else ""
            tags_str = f" [{', '.join(col.tags)}]" if col.tags else ""
            lines.append(f"- **{col.name}**{type_str}{desc}{tags_str}")
        lines.append("")
    if brief.joins:
        lines.append("## Joins")
        for jp in brief.joins:
            on_str = ", ".join(f"{a} = {b}" for a, b in jp.on)
            type_str = f" ({jp.type})" if jp.type else ""
            lines.append(f"- → {jp.to_table}{type_str}: {on_str}")
        lines.append("")
    if brief.query_patterns:
        lines.append("## Query Patterns")
        for qp in brief.query_patterns:
            cols = ", ".join(qp.columns_used[:5])
            lines.append(f"- **{qp.source_model}** uses: {cols}")
        lines.append("")
    if brief.column_usage:
        lines.append("## Column Usage")
        for col_name, count in sorted(brief.column_usage.items(), key=lambda x: -x[1]):
            lines.append(f"- {col_name}: {count} downstream refs")
        lines.append("")
    if brief.field_confidence:
        lines.append("## Field Confidence")
        for field_name, score in sorted(brief.field_confidence.items()):
            lines.append(f"- {field_name}: {score:.2f}")
        lines.append("")
    lines.append("## Evidence")
    if brief.evidence:
        lines.extend(f"- {_format_evidence(ref)}" for ref in brief.evidence)
    else:
        lines.append("- none")
    return "\n".join(lines).strip()


def render_catalog_markdown(catalog: Catalog) -> str:
    body = [
        "# Table Brief Catalog",
        "",
        f"- Repo Root: `{catalog.repo_root}`",
        f"- Project Type: `{catalog.project_type}`",
        f"- Generated At: `{catalog.generated_at.isoformat()}`",
        "",
    ]
    for brief in catalog.briefs:
        body.append(render_brief_markdown(brief))
        body.append("")
    return "\n".join(body).strip()


def render_compare_json(result: CompareResult) -> str:
    return result.model_dump_json(indent=2)


def render_compare_markdown(result: CompareResult) -> str:
    lines = ["# Table Comparison", ""]
    table_names = [entry.table for entry in result.tables]
    lines.append(f"Comparing: {', '.join(table_names)}")
    lines.append("")
    if result.differences:
        lines.append("## Differences")
        lines.append("")
        for field_name, values in result.differences.items():
            lines.append(f"### {field_name}")
            for i, value in enumerate(values):
                lines.append(f"- **{table_names[i]}**: {value or 'unknown'}")
            lines.append("")
    else:
        lines.append("No differences found.")
        lines.append("")
    lines.append("## Full Briefs")
    lines.append("")
    for entry in result.tables:
        lines.append(render_brief_markdown(entry.brief))
        lines.append("")
    return "\n".join(lines).strip()


def render_search_json(result: SearchResult) -> str:
    return result.model_dump_json(indent=2)


def render_search_markdown(result: SearchResult) -> str:
    lines = [f"# Search: {result.query}", ""]
    if not result.hits:
        lines.append("No results found.")
        return "\n".join(lines).strip()
    lines.append(f"{len(result.hits)} result(s)")
    lines.append("")
    for i, hit in enumerate(result.hits, 1):
        purpose = hit.brief.purpose or "unknown"
        lines.append(f"## {i}. {hit.table}")
        lines.append(f"- Purpose: {purpose}")
        if hit.brief.grain:
            lines.append(f"- Grain: {hit.brief.grain}")
        lines.append(f"- Confidence: {hit.brief.confidence:.2f}")
        lines.append(f"- Rank: {hit.rank:.4f}")
        lines.append("")
    return "\n".join(lines).strip()


def render_lineage_json(result: LineageResult) -> str:
    return result.model_dump_json(indent=2)


def render_lineage_markdown(result: LineageResult) -> str:
    lines = [f"# Lineage: {result.origin}", ""]
    lines.append(f"Direction: {result.direction}")
    if result.max_depth is not None:
        lines.append(f"Max Depth: {result.max_depth}")
    lines.append("")
    if not result.nodes:
        lines.append("No lineage found.")
        return "\n".join(lines).strip()
    by_depth: dict[int, list[str]] = {}
    for node in result.nodes:
        by_depth.setdefault(node.depth, []).append(node.table)
    for depth in sorted(by_depth):
        indent = "  " * depth
        for table in sorted(by_depth[depth]):
            lines.append(f"{indent}{'└── ' if depth > 0 else ''}{table}")
    return "\n".join(lines).strip()


def _render_field(label: str, value: str | None) -> list[str]:
    return [f"## {label}", value if value else "unknown", ""]


def _format_evidence(ref: EvidenceRef) -> str:
    payload = {
        "file": ref.file,
        "start_line": ref.start_line,
        "end_line": ref.end_line,
        "kind": ref.kind,
    }
    return json.dumps(payload, ensure_ascii=True)
