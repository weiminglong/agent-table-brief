from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from agent_table_brief.models import Catalog, CliError, RepoSummary, TableBrief
from agent_table_brief.render import (
    render_brief_json,
    render_brief_markdown,
    render_catalog_json,
    render_catalog_markdown,
)
from agent_table_brief.repository import scan_repository
from agent_table_brief.storage import (
    CatalogStore,
    RepoAmbiguousError,
    RepoNotScannedError,
    resolve_store_path,
)

app = typer.Typer(help="Generate compact table briefs from dbt and SQL repositories.")


class ProjectType(StrEnum):
    auto = "auto"
    dbt = "dbt"
    sql = "sql"


class OutputFormat(StrEnum):
    json = "json"
    markdown = "markdown"


RepoArgument = Annotated[
    Path,
    typer.Argument(exists=True, file_okay=False, resolve_path=True),
]
RepoOption = Annotated[
    Path | None,
    typer.Option("--repo", exists=True, file_okay=False, resolve_path=True),
]
StoreOption = Annotated[Path | None, typer.Option("--store", dir_okay=False, resolve_path=True)]
OutputOption = Annotated[Path | None, typer.Option("--output")]
FormatOption = Annotated[OutputFormat, typer.Option("--format")]
ProjectTypeOption = Annotated[ProjectType, typer.Option("--project-type")]
TableArgument = Annotated[str, typer.Argument()]


@app.command()
def scan(
    path: RepoArgument = Path("."),
    project_type: ProjectTypeOption = ProjectType.auto,
    store: StoreOption = None,
) -> None:
    try:
        scanned_catalog = scan_repository(path, project_type=project_type.value)
        result = _store(store).store_scan(scanned_catalog)
    except Exception as exc:
        _fail("scan_failed", str(exc), {"path": str(path)})
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def brief(
    table: TableArgument,
    repo: RepoOption = None,
    store: StoreOption = None,
    format: FormatOption = OutputFormat.json,
) -> None:
    try:
        table_brief = _store(store).load_brief(table, repo_path=repo)
    except RepoNotScannedError as exc:
        _fail("repo_not_scanned", str(exc), {"repo": _repo_detail(repo)})
    except RepoAmbiguousError as exc:
        _fail("repo_ambiguous", str(exc), {"repo": _repo_detail(repo)})
    except KeyError as exc:
        _fail("brief_not_found", str(exc), {"table": table, "repo": _repo_detail(repo)})
    except ValueError as exc:
        _fail("brief_ambiguous", str(exc), {"table": table, "repo": _repo_detail(repo)})
    except Exception as exc:
        _fail("brief_failed", str(exc), {"table": table, "repo": _repo_detail(repo)})
    typer.echo(_render_brief(table_brief, format))


@app.command()
def export(
    repo: RepoOption = None,
    store: StoreOption = None,
    format: FormatOption = OutputFormat.json,
    output: OutputOption = None,
) -> None:
    try:
        loaded_catalog = _store(store).load_catalog(repo_path=repo)
    except RepoNotScannedError as exc:
        _fail("repo_not_scanned", str(exc), {"repo": _repo_detail(repo)})
    except RepoAmbiguousError as exc:
        _fail("repo_ambiguous", str(exc), {"repo": _repo_detail(repo)})
    except Exception as exc:
        _fail("export_failed", str(exc), {"repo": _repo_detail(repo)})
    rendered = _render_catalog(loaded_catalog, format)
    if output is None:
        typer.echo(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    typer.echo(json.dumps({"output": str(output), "format": format.value}, indent=2))


@app.command()
def repos(store: StoreOption = None) -> None:
    try:
        summaries = _store(store).list_repos()
    except Exception as exc:
        _fail("repos_failed", str(exc))
    typer.echo(_render_json_list(summaries))


@app.command()
def gc(store: StoreOption = None) -> None:
    try:
        result = _store(store).gc()
    except Exception as exc:
        _fail("gc_failed", str(exc))
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def vacuum(store: StoreOption = None) -> None:
    try:
        result = _store(store).vacuum()
    except Exception as exc:
        _fail("vacuum_failed", str(exc))
    typer.echo(result.model_dump_json(indent=2))


def main() -> None:
    app()


def _store(store_path: Path | None) -> CatalogStore:
    return CatalogStore(resolve_store_path(store_path))


def _render_brief(brief: TableBrief, format: OutputFormat) -> str:
    if format is OutputFormat.markdown:
        return render_brief_markdown(brief)
    return render_brief_json(brief)


def _render_catalog(catalog: Catalog, format: OutputFormat) -> str:
    if format is OutputFormat.markdown:
        return render_catalog_markdown(catalog)
    return render_catalog_json(catalog)


def _render_json_list(items: list[RepoSummary]) -> str:
    return json.dumps([item.model_dump(mode="json") for item in items], indent=2)


def _repo_detail(repo: Path | None) -> str:
    return str(repo.resolve()) if repo is not None else str(Path.cwd())


def _fail(code: str, message: str, details: dict[str, Any] | None = None) -> None:
    payload = CliError(code=code, message=message, details=details or {})
    typer.echo(payload.model_dump_json(indent=2), err=True)
    raise typer.Exit(code=1)
