from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from agent_table_brief.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_scan_and_brief_json(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    result = runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["brief_count"] == 5
    assert payload["reused"] is False

    brief_result = runner.invoke(
        app,
        [
            "brief",
            "mart.daily_active_users",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert brief_result.exit_code == 0
    brief_payload = json.loads(brief_result.stdout)
    assert brief_payload["table"] == "mart.daily_active_users"


def test_scan_reuses_identical_repo(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["reused"] is True
    assert payload["brief_count"] == 4


def test_export_markdown(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    export_path = tmp_path / "briefs.md"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
        catch_exceptions=False,
    )

    result = runner.invoke(
        app,
        [
            "export",
            "--repo",
            str(FIXTURES / "sql_repo"),
            "--store",
            str(store_path),
            "--format",
            "markdown",
            "--output",
            str(export_path),
        ],
    )
    assert result.exit_code == 0
    assert "# Table Brief Catalog" in export_path.read_text(encoding="utf-8")


def test_brief_unknown_table_exits_non_zero(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "brief",
            "missing_table",
            "--repo",
            str(FIXTURES / "sql_repo"),
            "--store",
            str(store_path),
        ],
    )
    assert result.exit_code == 1
    error = json.loads(result.stderr)
    assert error["code"] == "brief_not_found"


def test_brief_unscanned_repo_returns_repo_not_scanned(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
        catch_exceptions=False,
    )

    unknown_repo = tmp_path / "empty"
    unknown_repo.mkdir()
    result = runner.invoke(
        app,
        [
            "brief",
            "marts.orders_by_day",
            "--repo",
            str(unknown_repo),
            "--store",
            str(store_path),
        ],
    )

    assert result.exit_code == 1
    error = json.loads(result.stderr)
    assert error["code"] == "repo_not_scanned"


def test_repos_lists_active_scans(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
        catch_exceptions=False,
    )

    result = runner.invoke(app, ["repos", "--store", str(store_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 2
    assert {item["project_type"] for item in payload} == {"dbt", "sql"}


def test_scan_reuses_when_unrelated_yaml_changes(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    repo_path = tmp_path / "sql_repo"
    shutil.copytree(FIXTURES / "sql_repo", repo_path)
    extra_yaml = repo_path / "notes.yml"
    extra_yaml.write_text("owner: analytics\n", encoding="utf-8")

    first = runner.invoke(
        app,
        ["scan", str(repo_path), "--store", str(store_path)],
        catch_exceptions=False,
    )
    assert first.exit_code == 0

    extra_yaml.write_text("owner: platform\n", encoding="utf-8")
    second = runner.invoke(
        app,
        ["scan", str(repo_path), "--store", str(store_path)],
        catch_exceptions=False,
    )

    payload = json.loads(second.stdout)
    assert payload["reused"] is True


def test_scan_reuses_across_git_clones(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    source_repo = tmp_path / "source_repo"
    clone_a = tmp_path / "clone_a"
    clone_b = tmp_path / "clone_b"
    shutil.copytree(FIXTURES / "sql_repo", source_repo)

    _git(source_repo, "init")
    _git(source_repo, "config", "user.email", "test@example.com")
    _git(source_repo, "config", "user.name", "Test User")
    _git(source_repo, "add", ".")
    _git(source_repo, "commit", "-m", "initial")
    _git(tmp_path, "clone", str(source_repo), str(clone_a))
    _git(tmp_path, "clone", str(source_repo), str(clone_b))

    first = runner.invoke(
        app,
        ["scan", str(clone_a), "--store", str(store_path)],
        catch_exceptions=False,
    )
    assert first.exit_code == 0

    second = runner.invoke(
        app,
        ["scan", str(clone_b), "--store", str(store_path)],
        catch_exceptions=False,
    )
    payload = json.loads(second.stdout)
    assert payload["reused"] is True

    repos_result = runner.invoke(app, ["repos", "--store", str(store_path)])
    repos_payload = json.loads(repos_result.stdout)
    assert len(repos_payload) == 1
    assert repos_payload[0]["effective_root"] == str(clone_b.resolve())


def test_compare_json_output(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "compare",
            "mart.daily_active_users",
            "mart.daily_active_users_all",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["tables"]) == 2
    assert "differences" in payload
    assert "filters_or_exclusions" in payload["differences"]


def test_compare_unknown_table_exits_non_zero(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "compare",
            "mart.daily_active_users",
            "nonexistent_table",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
        ],
    )
    assert result.exit_code == 1
    error = json.loads(result.stderr)
    assert error["code"] == "brief_not_found"


def test_brief_json_includes_field_confidence(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "brief",
            "mart.daily_active_users",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "field_confidence" in payload
    assert "purpose" in payload["field_confidence"]
    assert payload["field_confidence"]["purpose"] > 0.0


def test_export_markdown_includes_field_confidence(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "brief",
            "mart.daily_active_users",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "markdown",
        ],
    )
    assert result.exit_code == 0
    assert "Field Confidence" in result.stdout


def test_search_json_returns_ranked_results(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "search",
            "daily active users",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "daily active users"
    assert len(payload["hits"]) > 0
    tables = [hit["table"] for hit in payload["hits"]]
    assert any("daily_active_users" in t for t in tables)


def test_search_markdown_output(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "search",
            "daily active users",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "markdown",
        ],
    )
    assert result.exit_code == 0
    assert "# Search:" in result.stdout
    assert "result(s)" in result.stdout


def test_search_no_results(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "search",
            "zzzznonexistenttermzzzz",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["hits"]) == 0


def test_search_with_limit(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "dbt_project"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        app,
        [
            "search",
            "users",
            "--repo",
            str(FIXTURES / "dbt_project"),
            "--store",
            str(store_path),
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["hits"]) <= 1


def test_search_unscanned_repo_returns_error(tmp_path: Path) -> None:
    store_path = tmp_path / "store.db"
    runner.invoke(
        app,
        ["scan", str(FIXTURES / "sql_repo"), "--store", str(store_path)],
        catch_exceptions=False,
    )
    unknown_repo = tmp_path / "empty"
    unknown_repo.mkdir()
    result = runner.invoke(
        app,
        [
            "search",
            "orders",
            "--repo",
            str(unknown_repo),
            "--store",
            str(store_path),
        ],
    )
    assert result.exit_code == 1
    error = json.loads(result.stderr)
    assert error["code"] == "repo_not_scanned"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
