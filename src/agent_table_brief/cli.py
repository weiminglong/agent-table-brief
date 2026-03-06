from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from agent_table_brief.models import Catalog, TableBrief
from agent_table_brief.render import (
    render_brief_json,
    render_brief_markdown,
    render_catalog_json,
    render_catalog_markdown,
)
from agent_table_brief.repository import find_brief, load_catalog, save_catalog, scan_repository

app = typer.Typer(help="Generate compact table briefs from dbt and SQL repositories.")
DEFAULT_CATALOG = Path(".tablebrief/catalog.json")


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
CatalogOption = Annotated[
    Path,
    typer.Option("--catalog", exists=True, dir_okay=False),
]
CatalogWriteOption = Annotated[Path, typer.Option("--catalog")]
OutputOption = Annotated[Path | None, typer.Option("--output")]
FormatOption = Annotated[OutputFormat, typer.Option("--format")]
ProjectTypeOption = Annotated[ProjectType, typer.Option("--project-type")]
TableArgument = Annotated[str, typer.Argument()]


@app.command()
def scan(
    path: RepoArgument = Path("."),
    project_type: ProjectTypeOption = ProjectType.auto,
    catalog: CatalogWriteOption = DEFAULT_CATALOG,
) -> None:
    scanned_catalog = scan_repository(path, project_type=project_type.value)
    save_catalog(scanned_catalog, catalog)
    typer.echo(
        f"Scanned {len(scanned_catalog.briefs)} tables from {scanned_catalog.repo_root} "
        f"({scanned_catalog.project_type}) into {catalog}"
    )


@app.command()
def brief(
    table: TableArgument,
    catalog: CatalogOption = DEFAULT_CATALOG,
    format: FormatOption = OutputFormat.json,
) -> None:
    loaded_catalog = load_catalog(catalog)
    try:
        table_brief = find_brief(loaded_catalog, table)
    except (KeyError, ValueError) as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=1) from None
    typer.echo(_render_brief(table_brief, format))


@app.command()
def export(
    catalog: CatalogOption = DEFAULT_CATALOG,
    format: FormatOption = OutputFormat.json,
    output: OutputOption = None,
) -> None:
    loaded_catalog = load_catalog(catalog)
    rendered = _render_catalog(loaded_catalog, format)
    if output is None:
        typer.echo(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    typer.echo(f"Wrote {format.value} catalog to {output}")


def main() -> None:
    app()


def _render_brief(brief: TableBrief, format: OutputFormat) -> str:
    if format is OutputFormat.markdown:
        return render_brief_markdown(brief)
    return render_brief_json(brief)


def _render_catalog(catalog: Catalog, format: OutputFormat) -> str:
    if format is OutputFormat.markdown:
        return render_catalog_markdown(catalog)
    return render_catalog_json(catalog)


def _echo_error(message: str) -> None:
    typer.secho(message, err=True, fg=typer.colors.RED)
