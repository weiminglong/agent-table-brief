from __future__ import annotations

import json

from agent_table_brief.models import Catalog, EvidenceRef, TableBrief


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
