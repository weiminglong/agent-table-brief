from __future__ import annotations

from pathlib import Path

import pytest

from agent_table_brief.repository import (
    _clean_sql_for_parsing,
    _extract_sql_insights,
    detect_project_type,
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
