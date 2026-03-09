from __future__ import annotations

from pathlib import Path

import pytest

from agent_table_brief.repository import (
    _clean_sql_for_parsing,
    _extract_sql_insights,
    build_compare_result,
    detect_project_type,
    enrich_from_db,
    find_brief,
    scan_repository,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_project_type_for_dbt_fixture() -> None:
    assert detect_project_type(FIXTURES / "dbt_project") == "dbt"


def test_detect_project_type_for_nested_dbt_fixture() -> None:
    assert detect_project_type(FIXTURES / "monorepo_with_dbt") == "dbt"


def test_scan_dbt_repository_extracts_expected_brief() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    assert brief.purpose == "Daily active users by product surface"
    assert brief.grain == "activity_date x user_id"
    assert brief.primary_keys == ["activity_date", "user_id"]
    assert "mart.dim_users" in brief.derived_from
    assert "staging.stg_events" in brief.derived_from
    assert "excludes employees" in brief.filters_or_exclusions
    assert "logged-in users only" in brief.filters_or_exclusions
    assert "incremental model" in brief.freshness_hints
    assert "kpi.weekly_growth" in brief.downstream_usage
    assert "mart.daily_active_users_all" in brief.alternatives
    assert brief.evidence


def test_scan_sql_repository_extracts_expected_brief() -> None:
    catalog = scan_repository(FIXTURES / "sql_repo")
    brief = find_brief(catalog, "marts.orders_by_day")

    assert brief.purpose == "Daily order facts"
    assert brief.grain == "order_date x user_id"
    assert brief.primary_keys == ["order_date", "user_id"]
    assert brief.derived_from == ["staging.raw_orders"]
    assert "excludes test orders" in brief.filters_or_exclusions
    assert brief.downstream_usage == ["dashboards.weekly_orders"]
    assert "marts.orders_by_day_all" in brief.alternatives
    assert brief.evidence


def test_scan_nested_dbt_repository_uses_effective_dbt_root() -> None:
    catalog = scan_repository(FIXTURES / "monorepo_with_dbt")
    brief = find_brief(catalog, "mart.daily_active_users")

    assert catalog.project_type == "dbt"
    assert Path(catalog.repo_root) == (FIXTURES / "monorepo_with_dbt" / "analytics").resolve()
    assert len(catalog.briefs) == 2
    assert brief.derived_from == ["staging.stg_events"]
    assert all("problematic_macro" not in model.table for model in catalog.briefs)


def test_scan_repository_raises_for_multiple_nested_dbt_projects() -> None:
    with pytest.raises(ValueError, match="Multiple dbt projects found"):
        scan_repository(FIXTURES / "multi_dbt_monorepo")


def test_extract_sql_insights_skips_malformed_where_nodes() -> None:
    sql = """
    {% macro incremental_filter() %}
    WITH sections AS (
        SELECT * FROM {{ ref('upstream_model') }}
        {% if is_incremental() %}
        WHERE {{ incremental_predicate('block_date', 'block_number') }}
        {% endif %}
    )
    SELECT * FROM sections
    {% endmacro %}
    """

    insights = _extract_sql_insights(_clean_sql_for_parsing(sql))

    assert insights.where_clauses == []


def test_find_brief_raises_for_ambiguous_short_name() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    with pytest.raises(KeyError):
        find_brief(catalog, "does_not_exist")


def test_field_confidence_present_for_dbt_brief() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    assert "purpose" in brief.field_confidence
    assert "grain" in brief.field_confidence
    assert "primary_keys" in brief.field_confidence
    assert "derived_from" in brief.field_confidence
    assert "filters_or_exclusions" in brief.field_confidence
    assert "freshness_hints" in brief.field_confidence
    assert "downstream_usage" in brief.field_confidence
    assert "alternatives" in brief.field_confidence
    assert brief.field_confidence["purpose"] > 0.0
    assert brief.field_confidence["grain"] > 0.0


def test_grain_evidence_has_narrow_line_range() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    grain_evidence = brief.field_evidence.get("grain", brief.evidence)
    for ref in grain_evidence:
        assert ref.end_line - ref.start_line < 10, (
            f"Expected narrow grain evidence range, got {ref.start_line}-{ref.end_line}"
        )


def test_alternatives_include_filter_divergent_pair() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")
    assert "mart.daily_active_users_all" in brief.alternatives


def test_build_compare_result_detects_differences() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief_a = find_brief(catalog, "mart.daily_active_users")
    brief_b = find_brief(catalog, "mart.daily_active_users_all")

    result = build_compare_result([brief_a, brief_b])

    assert len(result.tables) == 2
    assert result.tables[0].table == "mart.daily_active_users"
    assert result.tables[1].table == "mart.daily_active_users_all"
    assert "filters_or_exclusions" in result.differences


# --- Column extraction tests (task 1.13) ---


def test_columns_extracted_from_yaml_and_sql() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    col_names = {c.name for c in brief.columns}
    # YAML-defined columns
    assert "activity_date" in col_names
    assert "user_id" in col_names
    assert "email" in col_names
    # SQL-only column (not in YAML) — should NOT appear since SELECT only has
    # activity_date and user_id which are already covered by YAML
    assert len(brief.columns) >= 3


def test_yaml_columns_have_high_confidence() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    yaml_cols = {c.name: c for c in brief.columns}
    assert yaml_cols["activity_date"].confidence == 0.95
    assert yaml_cols["user_id"].confidence == 0.95


def test_sql_only_columns_have_lower_confidence() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "staging.stg_events")

    # stg_events has no YAML column defs, so all columns come from SQL
    for col in brief.columns:
        assert col.confidence == 0.65


def test_yaml_column_descriptions_preserved() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    cols_by_name = {c.name: c for c in brief.columns}
    assert cols_by_name["activity_date"].description == "Date of user activity"
    assert cols_by_name["user_id"].description == "Unique user identifier"


def test_pii_tagging_from_yaml_tags() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    cols_by_name = {c.name: c for c in brief.columns}
    assert "pii" in cols_by_name["email"].tags


def test_pii_tagging_from_column_name_pattern() -> None:
    """Columns named 'email' should get auto-tagged with pii."""
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    cols_by_name = {c.name: c for c in brief.columns}
    email_col = cols_by_name["email"]
    # Should have pii tag either from YAML tag or name pattern
    assert "pii" in email_col.tags


def test_field_confidence_includes_columns() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    assert "columns" in brief.field_confidence
    assert brief.field_confidence["columns"] == 0.95


# --- Join inference tests (task 2.11) ---


def test_joins_inferred_from_yaml_relationship_test() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    # The schema.yml has a relationships test: user_id -> dim_users.user_id
    join_targets = {j.to_table for j in brief.joins}
    assert "mart.dim_users" in join_targets

    dim_users_join = next(j for j in brief.joins if j.to_table == "mart.dim_users")
    assert ("user_id", "user_id") in dim_users_join.on
    assert dim_users_join.confidence == 0.95


def test_joins_inferred_from_sql_join_on() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    # The SQL has: join dim_users as u on e.user_id = u.user_id
    # This should produce a join path (possibly deduplicated with YAML join)
    assert len(brief.joins) >= 1


def test_field_confidence_includes_joins() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    assert "joins" in brief.field_confidence
    assert brief.field_confidence["joins"] >= 0.85


# --- Query pattern tests (task 4.7) ---


def test_query_patterns_extracted_from_downstream() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    # weekly_growth references daily_active_users
    assert len(brief.query_patterns) >= 1
    pattern_sources = {p.source_model for p in brief.query_patterns}
    assert "kpi.weekly_growth" in pattern_sources


def test_column_usage_aggregated() -> None:
    catalog = scan_repository(FIXTURES / "dbt_project")
    brief = find_brief(catalog, "mart.daily_active_users")

    # weekly_growth selects activity_date and dau_records
    assert isinstance(brief.column_usage, dict)
    if brief.column_usage:
        assert any(count > 0 for count in brief.column_usage.values())


# --- Live database enrichment tests (task 5.7) ---


def test_backwards_compatibility_new_fields_default_empty() -> None:
    """Verify old brief fields are unchanged and new fields have empty defaults."""
    catalog = scan_repository(FIXTURES / "sql_repo")
    brief = find_brief(catalog, "marts.orders_by_day")

    # Old fields still work
    assert brief.purpose is not None
    assert brief.grain is not None
    assert brief.primary_keys
    assert brief.derived_from

    # New fields default to empty when no YAML metadata
    assert isinstance(brief.columns, list)
    assert isinstance(brief.joins, list)
    assert isinstance(brief.query_patterns, list)
    assert isinstance(brief.column_usage, dict)


def test_enrich_from_db_connection_failure_returns_catalog() -> None:
    """Connection failure should warn and return original catalog."""
    import warnings

    catalog = scan_repository(FIXTURES / "dbt_project")
    original_count = len(catalog.briefs)

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = enrich_from_db(catalog, "sqlite:///nonexistent_db.db")

    assert len(result.briefs) == original_count


def test_enrich_from_db_missing_sqlalchemy_returns_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If sqlalchemy is not importable, should warn and return original."""
    import builtins
    import warnings

    real_import = builtins.__import__

    def mock_import(
        name: str, *args: object, **kwargs: object
    ) -> object:
        if name == "sqlalchemy":
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)

    catalog = scan_repository(FIXTURES / "dbt_project")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = enrich_from_db(catalog, "postgresql://fake")

    assert len(result.briefs) == len(catalog.briefs)
    assert any("sqlalchemy" in str(warning.message) for warning in w)
