from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agent_table_brief.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_scan_and_brief_json(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    result = runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--catalog", str(catalog_path)],
    )
    assert result.exit_code == 0
    assert catalog_path.exists()

    brief_result = runner.invoke(
        app,
        ["brief", "mart.daily_active_users", "--catalog", str(catalog_path), "--format", "json"],
    )
    assert brief_result.exit_code == 0
    payload = json.loads(brief_result.stdout)
    assert payload["table"] == "mart.daily_active_users"


def test_export_markdown(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    export_path = tmp_path / "briefs.md"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--catalog", str(catalog_path)],
        catch_exceptions=False,
    )

    result = runner.invoke(
        app,
        [
            "export",
            "--catalog",
            str(catalog_path),
            "--format",
            "markdown",
            "--output",
            str(export_path),
        ],
    )
    assert result.exit_code == 0
    assert "# Table Brief Catalog" in export_path.read_text(encoding="utf-8")


def test_brief_unknown_table_exits_non_zero(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--catalog", str(catalog_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        ["brief", "missing_table", "--catalog", str(catalog_path)],
    )
    assert result.exit_code == 1
