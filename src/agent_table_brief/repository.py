from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml
from sqlglot import exp, parse_one
from sqlglot.errors import ErrorLevel, ParseError

from agent_table_brief import __version__
from agent_table_brief.models import Catalog, EvidenceRef, TableBrief

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tablebrief",
    ".venv",
    "__pycache__",
    "build",
    "dbt_packages",
    "dist",
    "node_modules",
    "target",
}

DBT_REF_RE = re.compile(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)")
DBT_SOURCE_RE = re.compile(
    r"source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
)
DBT_CONFIG_RE = re.compile(r"\{\{\s*config\((?P<body>.*?)\)\s*\}\}", re.DOTALL)
KEY_VALUE_RE = re.compile(r"(?P<key>\w+)\s*=\s*['\"](?P<value>[^'\"]+)['\"]")
JINJA_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
FILTER_TERMS = ("employee", "internal", "bot", "test", "deleted", "logged", "sandbox")
TIME_HINTS = {
    "hour": "likely hourly batch",
    "hourly": "likely hourly batch",
    "day": "likely daily batch",
    "daily": "likely daily batch",
    "week": "likely weekly batch",
    "weekly": "likely weekly batch",
    "month": "likely monthly batch",
    "monthly": "likely monthly batch",
}
NAME_PREFIXES = ("stg_", "int_", "fct_", "dim_", "mart_", "kpi_")


@dataclass
class YamlMetadata:
    path: Path
    relative_path: str
    description: str | None = None
    unique_columns: set[str] = field(default_factory=set)
    not_null_columns: set[str] = field(default_factory=set)
    composite_keys: list[list[str]] = field(default_factory=list)


@dataclass
class ManifestMetadata:
    description: str | None = None
    alias: str | None = None
    schema_name: str | None = None
    materialized: str | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class SqlInsights:
    table_refs: set[str] = field(default_factory=set)
    group_by: list[str] = field(default_factory=list)
    where_clauses: list[str] = field(default_factory=list)


@dataclass
class DiscoveredModel:
    table: str
    short_name: str
    relative_path: str
    path: Path
    sql_text: str
    description: str | None
    top_comment: str | None
    materialized: str | None
    group_by: list[str]
    unique_columns: set[str]
    not_null_columns: set[str]
    composite_keys: list[list[str]]
    raw_dependencies: list[str]
    filters: list[str]
    freshness_hints: list[str]
    purpose_evidence: list[EvidenceRef]
    grain_evidence: list[EvidenceRef]
    key_evidence: list[EvidenceRef]
    dependency_evidence: list[EvidenceRef]
    filter_evidence: list[EvidenceRef]
    freshness_evidence: list[EvidenceRef]
    filename_evidence: EvidenceRef


def detect_project_type(root: Path) -> str:
    if (root / "dbt_project.yml").exists():
        return "dbt"
    if list(_iter_files(root, suffixes={".sql"}, include_target=False)):
        return "sql"
    raise ValueError(f"No SQL files found under {root}")


def scan_repository(root: Path, project_type: str = "auto") -> Catalog:
    resolved_root = root.resolve()
    detected_project_type = (
        detect_project_type(resolved_root) if project_type == "auto" else project_type
    )
    yaml_metadata = _load_yaml_metadata(resolved_root)
    manifest_metadata = _load_manifest_metadata(resolved_root)
    models = [
        _discover_model(
            path,
            resolved_root,
            detected_project_type,
            yaml_metadata,
            manifest_metadata,
        )
        for path in _iter_files(resolved_root, suffixes={".sql"})
    ]
    name_lookup = _build_name_lookup(models)
    normalized_deps = {
        model.table: _normalize_dependencies(model.raw_dependencies, name_lookup)
        for model in models
    }
    downstream = _build_downstream_map(normalized_deps)
    briefs = [_build_brief(model, models, normalized_deps, downstream) for model in models]
    briefs.sort(key=lambda brief: brief.table)
    return Catalog(
        repo_root=str(resolved_root),
        project_type=detected_project_type,
        generated_at=datetime.now(UTC),
        version=__version__,
        briefs=briefs,
    )


def save_catalog(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_catalog(path: Path) -> Catalog:
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))


def find_brief(catalog: Catalog, table_name: str) -> TableBrief:
    exact = [brief for brief in catalog.briefs if brief.table == table_name]
    if exact:
        return exact[0]
    short_matches = [brief for brief in catalog.briefs if brief.table.split(".")[-1] == table_name]
    if len(short_matches) == 1:
        return short_matches[0]
    if len(short_matches) > 1:
        options = ", ".join(sorted(brief.table for brief in short_matches))
        raise ValueError(f"Table name is ambiguous: {table_name}. Matches: {options}")
    raise KeyError(f"Table not found in catalog: {table_name}")


def _discover_model(
    path: Path,
    root: Path,
    project_type: str,
    yaml_metadata: dict[str, YamlMetadata],
    manifest_metadata: dict[str, ManifestMetadata],
) -> DiscoveredModel:
    relative_path = path.relative_to(root).as_posix()
    sql_text = path.read_text(encoding="utf-8")
    yaml_meta = yaml_metadata.get(
        path.stem,
        YamlMetadata(path=path, relative_path=relative_path),
    )
    manifest_meta = manifest_metadata.get(
        relative_path,
        manifest_metadata.get(path.stem, ManifestMetadata()),
    )
    config = _parse_config(sql_text)
    schema_name = (
        manifest_meta.schema_name
        or config.get("schema")
        or _infer_schema_name(path, root, project_type)
    )
    short_name = manifest_meta.alias or config.get("alias") or path.stem
    table_name = f"{schema_name}.{short_name}" if schema_name else short_name
    top_comment = _extract_top_comment(sql_text)
    cleaned_sql = _clean_sql_for_parsing(sql_text)
    insights = _extract_sql_insights(cleaned_sql)
    raw_dependencies = _extract_raw_dependencies(sql_text, insights) + manifest_meta.dependencies
    raw_dependencies = sorted(dict.fromkeys(raw_dependencies))
    description, purpose_evidence = _derive_description(
        relative_path,
        sql_text,
        yaml_meta,
        manifest_meta,
        top_comment,
    )
    materialized = manifest_meta.materialized or config.get("materialized")
    filters, filter_evidence = _derive_filters(
        relative_path,
        sql_text,
        insights.where_clauses,
    )
    freshness_hints, freshness_evidence = _derive_freshness_hints(
        relative_path,
        sql_text,
        materialized,
    )
    grain_evidence = [_make_file_evidence(relative_path, sql_text, "sql")]
    key_evidence = [_make_file_evidence(relative_path, sql_text, "sql")]
    dependency_evidence = _dependency_evidence(relative_path, sql_text, raw_dependencies)
    return DiscoveredModel(
        table=table_name,
        short_name=short_name,
        relative_path=relative_path,
        path=path,
        sql_text=sql_text,
        description=description,
        top_comment=top_comment,
        materialized=materialized,
        group_by=insights.group_by,
        unique_columns=yaml_meta.unique_columns,
        not_null_columns=yaml_meta.not_null_columns,
        composite_keys=yaml_meta.composite_keys,
        raw_dependencies=raw_dependencies,
        filters=filters,
        freshness_hints=freshness_hints,
        purpose_evidence=purpose_evidence,
        grain_evidence=grain_evidence,
        key_evidence=key_evidence,
        dependency_evidence=dependency_evidence,
        filter_evidence=filter_evidence,
        freshness_evidence=freshness_evidence,
        filename_evidence=EvidenceRef(
            file=relative_path,
            start_line=1,
            end_line=1,
            kind="filename",
        ),
    )


def _build_brief(
    model: DiscoveredModel,
    all_models: list[DiscoveredModel],
    normalized_deps: dict[str, list[str]],
    downstream: dict[str, list[str]],
) -> TableBrief:
    purpose, purpose_score = _infer_purpose(model)
    grain, grain_score = _infer_grain(model)
    primary_keys, key_score = _infer_primary_keys(model)
    derived_from = normalized_deps[model.table]
    dependency_score = 0.95 if derived_from else 0.0
    downstream_usage = downstream.get(model.table, [])
    downstream_score = 0.9 if downstream_usage else 0.0
    alternatives = _infer_alternatives(model, all_models, normalized_deps)
    alternatives_score = 0.8 if alternatives else 0.0
    filters_score = 0.9 if model.filters else 0.0
    freshness_score = 0.9 if model.freshness_hints else 0.0

    field_evidence: dict[str, list[EvidenceRef]] = {
        "purpose": model.purpose_evidence if purpose else [],
        "grain": model.grain_evidence if grain else [],
        "primary_keys": model.key_evidence if primary_keys else [],
        "derived_from": model.dependency_evidence if derived_from else [],
        "filters_or_exclusions": model.filter_evidence if model.filters else [],
        "freshness_hints": model.freshness_evidence if model.freshness_hints else [],
        "downstream_usage": [model.filename_evidence] if downstream_usage else [],
        "alternatives": [model.filename_evidence] if alternatives else [],
    }
    confidence = _compute_confidence(
        purpose_score,
        grain_score,
        key_score,
        dependency_score,
        filters_score,
        freshness_score,
        downstream_score,
        alternatives_score,
    )
    evidence = _dedupe_evidence(
        [evidence for refs in field_evidence.values() for evidence in refs]
    )
    return TableBrief(
        table=model.table,
        purpose=purpose,
        grain=grain,
        primary_keys=primary_keys,
        derived_from=derived_from,
        filters_or_exclusions=model.filters,
        freshness_hints=model.freshness_hints,
        downstream_usage=downstream_usage,
        alternatives=alternatives,
        confidence=confidence,
        evidence=evidence,
        field_evidence=field_evidence,
    )


def _infer_purpose(model: DiscoveredModel) -> tuple[str | None, float]:
    if model.description:
        return model.description, 0.95
    if model.top_comment:
        return model.top_comment, 0.8
    return _humanize_name(model.short_name), 0.45


def _infer_grain(model: DiscoveredModel) -> tuple[str | None, float]:
    if model.composite_keys:
        return " x ".join(model.composite_keys[0]), 0.95
    if model.group_by:
        return " x ".join(model.group_by), 0.85
    key_like_columns = [
        column
        for column in sorted(model.unique_columns)
        if column.endswith(("_id", "_key"))
    ]
    if key_like_columns:
        return " x ".join(key_like_columns), 0.6
    return None, 0.0


def _infer_primary_keys(model: DiscoveredModel) -> tuple[list[str], float]:
    if model.composite_keys:
        return sorted(model.composite_keys[0]), 0.95
    unique_and_required = sorted(model.unique_columns.intersection(model.not_null_columns))
    if unique_and_required:
        return unique_and_required, 0.9
    group_by_keys = [
        column
        for column in model.group_by
        if column.endswith(("_id", "_key", "_date"))
    ]
    if group_by_keys:
        return group_by_keys, 0.65
    return [], 0.0


def _infer_alternatives(
    model: DiscoveredModel,
    all_models: list[DiscoveredModel],
    normalized_deps: dict[str, list[str]],
) -> list[str]:
    scored: list[tuple[float, str]] = []
    this_deps = set(normalized_deps[model.table])
    for other in all_models:
        if other.table == model.table:
            continue
        name_score = SequenceMatcher(None, model.short_name, other.short_name).ratio()
        other_deps = set(normalized_deps[other.table])
        dep_score = _jaccard_similarity(this_deps, other_deps)
        prefix_bonus = 0.1 if _shared_name_prefix(model.short_name, other.short_name) else 0.0
        score = (0.6 * name_score) + (0.3 * dep_score) + prefix_bonus
        if score >= 0.45:
            scored.append((score, other.table))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [table for _, table in scored[:3]]


def _compute_confidence(
    purpose_score: float,
    grain_score: float,
    key_score: float,
    dependency_score: float,
    filters_score: float,
    freshness_score: float,
    downstream_score: float,
    alternatives_score: float,
) -> float:
    weights = {
        "purpose": 0.2,
        "grain": 0.2,
        "keys": 0.15,
        "dependencies": 0.15,
        "filters": 0.1,
        "freshness": 0.05,
        "downstream": 0.05,
        "alternatives": 0.1,
    }
    weighted = (
        (purpose_score * weights["purpose"])
        + (grain_score * weights["grain"])
        + (key_score * weights["keys"])
        + (dependency_score * weights["dependencies"])
        + (filters_score * weights["filters"])
        + (freshness_score * weights["freshness"])
        + (downstream_score * weights["downstream"])
        + (alternatives_score * weights["alternatives"])
    )
    return round(min(weighted, 0.99), 2)


def _build_name_lookup(models: list[DiscoveredModel]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    short_name_counts: defaultdict[str, int] = defaultdict(int)
    for model in models:
        short_name_counts[model.short_name] += 1
    for model in models:
        lookup[model.table] = model.table
        if short_name_counts[model.short_name] == 1:
            lookup[model.short_name] = model.table
    return lookup


def _normalize_dependencies(raw_dependencies: list[str], name_lookup: dict[str, str]) -> list[str]:
    normalized = [name_lookup.get(dependency, dependency) for dependency in raw_dependencies]
    return sorted(dict.fromkeys(normalized))


def _build_downstream_map(normalized_deps: dict[str, list[str]]) -> dict[str, list[str]]:
    downstream: dict[str, list[str]] = defaultdict(list)
    for table, dependencies in normalized_deps.items():
        for dependency in dependencies:
            downstream[dependency].append(table)
    for refs in downstream.values():
        refs.sort()
    return dict(downstream)


def _load_yaml_metadata(root: Path) -> dict[str, YamlMetadata]:
    metadata: dict[str, YamlMetadata] = {}
    for path in _iter_files(root, suffixes={".yml", ".yaml"}):
        relative_path = path.relative_to(root).as_posix()
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(document, dict):
                continue
            for collection_name in ("models", "tables"):
                entries = document.get(collection_name)
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                        continue
                    name = entry["name"]
                    current = metadata.get(
                        name,
                        YamlMetadata(path=path, relative_path=relative_path),
                    )
                    metadata[name] = _merge_yaml_metadata(
                        current,
                        _yaml_entry_to_metadata(path, relative_path, entry),
                    )
    return metadata


def _yaml_entry_to_metadata(path: Path, relative_path: str, entry: dict[str, Any]) -> YamlMetadata:
    metadata = YamlMetadata(
        path=path,
        relative_path=relative_path,
        description=entry.get("description"),
    )
    for test in entry.get("tests", []):
        if isinstance(test, dict):
            for value in test.values():
                if isinstance(value, dict):
                    columns = value.get("combination_of_columns") or value.get("column_names")
                    if isinstance(columns, list) and all(
                        isinstance(column, str) for column in columns
                    ):
                        metadata.composite_keys.append(columns)
    for column in entry.get("columns", []):
        if not isinstance(column, dict):
            continue
        column_name = column.get("name")
        if not isinstance(column_name, str):
            continue
        for test in column.get("tests", []):
            if test == "unique":
                metadata.unique_columns.add(column_name)
            if test == "not_null":
                metadata.not_null_columns.add(column_name)
    return metadata


def _merge_yaml_metadata(left: YamlMetadata, right: YamlMetadata) -> YamlMetadata:
    merged = YamlMetadata(
        path=left.path,
        relative_path=left.relative_path,
        description=left.description or right.description,
    )
    merged.unique_columns = left.unique_columns | right.unique_columns
    merged.not_null_columns = left.not_null_columns | right.not_null_columns
    merged.composite_keys = left.composite_keys + right.composite_keys
    return merged


def _load_manifest_metadata(root: Path) -> dict[str, ManifestMetadata]:
    manifest_path = root / "target" / "manifest.json"
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = payload.get("nodes", {})
    metadata: dict[str, ManifestMetadata] = {}
    for node in nodes.values():
        if not isinstance(node, dict) or node.get("resource_type") != "model":
            continue
        original_path = node.get("original_file_path")
        if not isinstance(original_path, str):
            continue
        dependencies = []
        depends_on = node.get("depends_on", {})
        for dependency in depends_on.get("nodes", []):
            if not isinstance(dependency, str):
                continue
            parts = dependency.split(".")
            dependencies.append(".".join(parts[-2:]) if parts[0] == "source" else parts[-1])
        metadata[original_path] = ManifestMetadata(
            description=node.get("description"),
            alias=node.get("alias"),
            schema_name=node.get("schema"),
            materialized=node.get("config", {}).get("materialized"),
            dependencies=dependencies,
        )
    return metadata


def _parse_config(sql_text: str) -> dict[str, str]:
    match = DBT_CONFIG_RE.search(sql_text)
    if not match:
        return {}
    return {
        item.group("key"): item.group("value")
        for item in KEY_VALUE_RE.finditer(match.group("body"))
    }


def _extract_raw_dependencies(sql_text: str, insights: SqlInsights) -> list[str]:
    dependencies = [match.group(1) for match in DBT_REF_RE.finditer(sql_text)]
    dependencies.extend(
        f"{match.group(1)}.{match.group(2)}"
        for match in DBT_SOURCE_RE.finditer(sql_text)
    )
    dependencies.extend(sorted(insights.table_refs))
    return sorted(dict.fromkeys(dependencies))


def _derive_description(
    relative_path: str,
    sql_text: str,
    yaml_meta: YamlMetadata,
    manifest_meta: ManifestMetadata,
    top_comment: str | None,
) -> tuple[str | None, list[EvidenceRef]]:
    if yaml_meta.description:
        return yaml_meta.description, [
            _make_fragment_evidence(
                yaml_meta.relative_path,
                yaml_meta.path,
                yaml_meta.description,
                "yaml",
            )
        ]
    if manifest_meta.description:
        return manifest_meta.description, [_make_file_evidence(relative_path, sql_text, "manifest")]
    if top_comment:
        return top_comment, [
            _make_fragment_evidence(relative_path, None, top_comment, "comment", sql_text)
        ]
    return None, [_make_file_evidence(relative_path, sql_text, "filename")]


def _derive_filters(
    relative_path: str,
    sql_text: str,
    where_clauses: list[str],
) -> tuple[list[str], list[EvidenceRef]]:
    hints: list[str] = []
    evidence: list[EvidenceRef] = []
    for clause in where_clauses:
        for subclause in re.split(r"\bAND\b", clause, flags=re.IGNORECASE):
            if any(term in subclause.lower() for term in FILTER_TERMS):
                hints.append(_normalize_filter_hint(subclause))
                evidence.append(
                    _make_fragment_evidence(relative_path, None, subclause, "sql", sql_text)
                )
    for comment_line in _extract_filter_comment_lines(sql_text):
        hints.append(_normalize_filter_hint(comment_line))
        evidence.append(
            _make_fragment_evidence(relative_path, None, comment_line, "comment", sql_text)
        )
    return list(dict.fromkeys(hints)), _dedupe_evidence(evidence)


def _derive_freshness_hints(
    relative_path: str,
    sql_text: str,
    materialized: str | None,
) -> tuple[list[str], list[EvidenceRef]]:
    hints: list[str] = []
    evidence: list[EvidenceRef] = []
    lowered = sql_text.lower()
    if materialized == "incremental":
        hints.append("incremental model")
        evidence.append(_make_file_evidence(relative_path, sql_text, "sql"))
    elif materialized:
        hints.append(f"{materialized} materialization")
        evidence.append(_make_file_evidence(relative_path, sql_text, "sql"))
    for token, hint in TIME_HINTS.items():
        if token in lowered or token in relative_path.lower():
            hints.append(hint)
            evidence.append(_make_file_evidence(relative_path, sql_text, "sql"))
            break
    return list(dict.fromkeys(hints)), _dedupe_evidence(evidence)


def _infer_schema_name(path: Path, root: Path, project_type: str) -> str | None:
    relative_parts = path.relative_to(root).parts
    if project_type == "dbt" and len(relative_parts) >= 3 and relative_parts[0] == "models":
        return relative_parts[1]
    if len(relative_parts) >= 2:
        return relative_parts[-2]
    return None


def _clean_sql_for_parsing(sql_text: str) -> str:
    cleaned = DBT_CONFIG_RE.sub("", sql_text)
    cleaned = DBT_REF_RE.sub(lambda match: match.group(1), cleaned)
    cleaned = DBT_SOURCE_RE.sub(lambda match: f"{match.group(1)}.{match.group(2)}", cleaned)
    cleaned = JINJA_RE.sub(" ", cleaned)
    return cleaned


def _extract_sql_insights(cleaned_sql: str) -> SqlInsights:
    try:
        expression = parse_one(cleaned_sql, error_level=ErrorLevel.IGNORE)
    except ParseError:
        return SqlInsights()
    if expression is None:
        return SqlInsights()
    cte_names = {cte.alias_or_name for cte in expression.find_all(exp.CTE)}
    table_refs = set()
    for table in expression.find_all(exp.Table):
        reference = ".".join(part for part in (table.catalog, table.db, table.name) if part)
        if table.name not in cte_names and reference:
            table_refs.add(reference)
    group_by: list[str] = []
    group = expression.args.get("group")
    if isinstance(group, exp.Group):
        group_by = [_normalize_identifier(item.sql()) for item in group.expressions]
    where_clauses = [where.this.sql() for where in expression.find_all(exp.Where)]
    return SqlInsights(table_refs=table_refs, group_by=group_by, where_clauses=where_clauses)


def _extract_top_comment(sql_text: str) -> str | None:
    lines = sql_text.splitlines()
    comment_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if comment_lines:
                break
            continue
        if stripped.startswith("{{"):
            continue
        if stripped.startswith("--"):
            comment_lines.append(stripped.removeprefix("--").strip())
            continue
        break
    return " ".join(comment_lines) if comment_lines else None


def _extract_filter_comment_lines(sql_text: str) -> list[str]:
    lines: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("--"):
            continue
        comment = stripped.removeprefix("--").strip()
        lowered = comment.lower()
        if "exclude" in lowered or "only" in lowered:
            lines.append(comment)
    return lines


def _dependency_evidence(
    relative_path: str,
    sql_text: str,
    dependencies: list[str],
) -> list[EvidenceRef]:
    if dependencies:
        return [_make_file_evidence(relative_path, sql_text, "sql")]
    return []


def _make_file_evidence(relative_path: str, text: str, kind: str) -> EvidenceRef:
    line_count = max(text.count("\n") + 1, 1)
    return EvidenceRef(file=relative_path, start_line=1, end_line=line_count, kind=kind)


def _make_fragment_evidence(
    relative_path: str,
    source_path: Path | None,
    fragment: str,
    kind: str,
    text: str | None = None,
) -> EvidenceRef:
    effective_text = text
    effective_path = relative_path
    if source_path is not None:
        effective_text = source_path.read_text(encoding="utf-8")
    if effective_text is None:
        return EvidenceRef(file=effective_path, start_line=1, end_line=1, kind=kind)
    index = effective_text.find(fragment)
    if index < 0:
        return EvidenceRef(file=effective_path, start_line=1, end_line=1, kind=kind)
    start_line = effective_text.count("\n", 0, index) + 1
    end_line = effective_text.count("\n", 0, index + len(fragment)) + 1
    return EvidenceRef(file=effective_path, start_line=start_line, end_line=end_line, kind=kind)


def _dedupe_evidence(evidence: list[EvidenceRef]) -> list[EvidenceRef]:
    seen: set[tuple[str, int, int, str]] = set()
    deduped: list[EvidenceRef] = []
    for item in evidence:
        key = (item.file, item.start_line, item.end_line, item.kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _humanize_name(name: str) -> str:
    normalized = name
    for prefix in NAME_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    words = normalized.replace(".", "_").split("_")
    phrase = " ".join(word for word in words if word)
    return phrase[:1].upper() + phrase[1:] if phrase else name


def _normalize_filter_hint(clause: str) -> str:
    lowered = clause.lower()
    if "employee" in lowered and any(
        token in lowered for token in ("false", "!=", "not", "exclude")
    ):
        return "excludes employees"
    if "internal" in lowered and any(
        token in lowered for token in ("false", "!=", "not", "exclude")
    ):
        return "excludes internal users"
    if "logged_in" in lowered and "true" in lowered:
        return "logged-in users only"
    if "logged-in" in lowered and "only" in lowered:
        return "logged-in users only"
    if "test" in lowered and any(token in lowered for token in ("false", "!=", "not", "exclude")):
        return "excludes test orders"
    compact = re.sub(r"\s+", " ", clause.strip())
    return compact[:120]


def _normalize_identifier(identifier: str) -> str:
    normalized = identifier.replace('"', "").replace("`", "")
    if "." in normalized:
        return normalized.split(".")[-1]
    return normalized


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _shared_name_prefix(left: str, right: str) -> bool:
    left_parts = left.split("_")
    right_parts = right.split("_")
    return len(left_parts) > 1 and len(right_parts) > 1 and left_parts[0] == right_parts[0]


def _iter_files(root: Path, suffixes: set[str], include_target: bool = True) -> list[Path]:
    results: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            if include_target and "target" in path.parts and path.suffix in suffixes:
                pass
            else:
                continue
        results.append(path)
    return sorted(results)
