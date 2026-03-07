from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agent_table_brief.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _scan(store_path: Path, fixture: str = "dbt_project") -> None:
    runner.invoke(
        app,
        ["scan", str(FIXTURES / fixture), "--store", str(store_path)],
        catch_exceptions=False,
    )


def test_search_tables_tool(tmp_path: Path) -> None:
    import os

    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import search_tables

        raw = search_tables(query="daily active users", repo=str(FIXTURES / "dbt_project"))
        result = json.loads(raw)
        assert result["query"] == "daily active users"
        assert len(result["hits"]) > 0
    finally:
        del os.environ["TABLEBRIEF_STORE"]


def test_get_brief_tool(tmp_path: Path) -> None:
    import os

    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import get_brief

        raw = get_brief(table="mart.daily_active_users", repo=str(FIXTURES / "dbt_project"))
        result = json.loads(raw)
        assert result["table"] == "mart.daily_active_users"
        assert "purpose" in result
    finally:
        del os.environ["TABLEBRIEF_STORE"]


def test_compare_tables_tool(tmp_path: Path) -> None:
    import os

    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import compare_tables

        raw = compare_tables(
            tables=["mart.daily_active_users", "mart.daily_active_users_all"],
            repo=str(FIXTURES / "dbt_project"),
        )
        result = json.loads(raw)
        assert len(result["tables"]) == 2
        assert "differences" in result
    finally:
        del os.environ["TABLEBRIEF_STORE"]


def test_list_tables_tool(tmp_path: Path) -> None:
    import os

    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import list_tables

        raw = list_tables(repo=str(FIXTURES / "dbt_project"))
        result = json.loads(raw)
        assert len(result) == 5
        assert all("table" in entry for entry in result)
    finally:
        del os.environ["TABLEBRIEF_STORE"]


def test_list_repos_tool(tmp_path: Path) -> None:
    import os

    store_path = tmp_path / "store.db"
    _scan(store_path)
    os.environ["TABLEBRIEF_STORE"] = str(store_path)
    try:
        from agent_table_brief.mcp_server import list_repos

        raw = list_repos()
        result = json.loads(raw)
        assert len(result) >= 1
        assert "repo_key" in result[0]
    finally:
        del os.environ["TABLEBRIEF_STORE"]


def test_serve_command_registered() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "store" in result.stdout.lower()
