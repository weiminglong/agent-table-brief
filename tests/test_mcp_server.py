from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_table_brief.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"

_has_mcp = pytest.importorskip is not None  # just for the flag below
try:
    import mcp  # noqa: F401

    _has_mcp = True
except ModuleNotFoundError:
    _has_mcp = False

requires_mcp = pytest.mark.skipif(not _has_mcp, reason="mcp extra not installed")


def _scan(store_path: Path, fixture: str = "dbt_project") -> None:
    runner.invoke(
        app,
        ["scan", str(FIXTURES / fixture), "--store", str(store_path)],
        catch_exceptions=False,
    )


@requires_mcp
def test_search_tables_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import search_tables

        result = search_tables(query="daily active users", repo=str(FIXTURES / "dbt_project"))
        assert result["query"] == "daily active users"
        assert len(result["hits"]) > 0
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_get_brief_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import get_brief

        result = get_brief(table="mart.daily_active_users", repo=str(FIXTURES / "dbt_project"))
        assert result["table"] == "mart.daily_active_users"
        assert "purpose" in result
        assert "columns" in result
        assert "joins" in result
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_compare_tables_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import compare_tables

        result = compare_tables(
            tables=["mart.daily_active_users", "mart.daily_active_users_all"],
            repo=str(FIXTURES / "dbt_project"),
        )
        assert len(result["tables"]) == 2
        assert "differences" in result
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_list_tables_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import list_tables

        result = list_tables(repo=str(FIXTURES / "dbt_project"))
        assert len(result["tables"]) == 5
        assert all("table" in entry for entry in result["tables"])
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_list_repos_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import list_repos

        result = list_repos()
        assert len(result["repos"]) >= 1
        assert "repo_key" in result["repos"][0]
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_get_columns_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import get_columns

        result = get_columns(table="mart.daily_active_users", repo=str(FIXTURES / "dbt_project"))
        assert result["table"] == "mart.daily_active_users"
        assert len(result["columns"]) >= 2
        col_names = {c["name"] for c in result["columns"]}
        assert "activity_date" in col_names
        assert "user_id" in col_names
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_get_join_path_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import get_join_path

        result = get_join_path(
            table_a="mart.daily_active_users",
            table_b="mart.dim_users",
            repo=str(FIXTURES / "dbt_project"),
        )
        assert result["from_table"] == "mart.daily_active_users"
        assert result["to_table"] == "mart.dim_users"
        assert result["found"] is True
        assert len(result["path"]) >= 1
    finally:
        del os.environ["TABLEBRIEF_STORE"]


@requires_mcp
def test_get_lineage_tool(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import get_lineage

        result = get_lineage(
            table="mart.daily_active_users",
            direction="both",
            repo=str(FIXTURES / "dbt_project"),
        )
        assert result["origin"] == "mart.daily_active_users"
        assert len(result["nodes"]) > 0
    finally:
        del os.environ["TABLEBRIEF_STORE"]


def test_serve_command_registered() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "store" in result.stdout.lower()
