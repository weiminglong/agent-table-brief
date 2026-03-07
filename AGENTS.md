# AGENTS.md

Instructions for AI agents working on this codebase.

## Quick orientation

`agent-table-brief` is a **Python CLI tool** (`tablebrief`) that scans dbt and SQL repositories
and produces structured "table briefs" -- compact JSON/Markdown summaries of each table's purpose,
grain, keys, dependencies, filters, and alternatives. There are no external services, databases,
or Docker containers needed. Everything runs locally with an embedded SQLite store.

**Package manager:** [uv](https://docs.astral.sh/uv/)
**CLI entry point:** `tablebrief` (defined in `pyproject.toml` → `agent_table_brief.cli:main`)
**Python source:** `src/agent_table_brief/`
**Tests:** `tests/`

## Cursor Cloud specific instructions

`uv` must be on `PATH` -- it is installed to `~/.local/bin` via `astral.sh/uv/install.sh` and
persisted in `~/.bashrc`. Source it if needed: `source ~/.bashrc`.

The SQLite store location defaults to `~/.local/state/tablebrief/store.db` on Linux. For isolated
testing, override with `--store /tmp/test_store.db` or set `TABLEBRIEF_HOME=/tmp/tb_test`.

The `uv_build` version constraint in `pyproject.toml` (`>=0.9.26,<0.10.0`) may emit a warning
with newer `uv` versions. This is cosmetic and does not affect functionality.

## Running quality checks

```bash
uv run ruff check .      # lint
uv run mypy src           # type check
uv run pytest             # tests
```

All three must pass before committing.

## Running the CLI

```bash
uv run tablebrief --help
uv run tablebrief scan <path-to-repo>
uv run tablebrief brief <table-name> --repo <path> --format json
uv run tablebrief compare <tableA> <tableB> --repo <path> --format json
uv run tablebrief search "<query>" --repo <path> --format json --limit 10
uv run tablebrief export --repo <path> --format markdown
uv run tablebrief serve   # MCP server (requires mcp extra)
```

## Architecture

```
src/agent_table_brief/
├── cli.py          # Typer CLI: all commands, option types, error output
├── models.py       # Pydantic models: TableBrief, Catalog, ScanResult, SearchResult, etc.
├── repository.py   # Core engine: scan repos, parse SQL, infer briefs
├── storage.py      # SQLite store: save/load catalogs, FTS5 search, GC
├── render.py       # Output formatting: JSON and Markdown renderers
└── mcp_server.py   # Optional MCP server (requires `mcp` extra)
```

### Data flow

```
CLI command → repository.scan_repository() → Catalog (Pydantic)
          → storage.CatalogStore.store_scan() → SQLite
          → render (JSON / Markdown) → stdout
```

### Key models (models.py)

| Model | Purpose |
|-------|---------|
| `TableBrief` | The core output: one table's purpose, grain, keys, deps, filters, etc. |
| `Catalog` | A collection of `TableBrief` objects from a single scan |
| `ScanResult` | Returned by `scan` command: repo info, scan ID, table list |
| `CompareResult` | Returned by `compare`: tables + field-level differences |
| `SearchResult` / `SearchHit` | Returned by `search`: ranked FTS5 results |
| `CliError` | Structured error output (code, message, details) |

### Table naming convention

Tables are qualified as `schema.model`:

- **dbt:** schema = subdirectory under `models/` (e.g., `models/mart/foo.sql` → `mart.foo`).
  `config(schema=..., alias=...)` and manifest metadata override directory-based naming.
- **SQL:** schema = parent directory of the `.sql` file.
- Short names (e.g., `daily_active_users`) work in lookups when unambiguous.

### Scanning heuristics

The scanner in `repository.py` infers brief fields using these signals:

| Field | Primary signal | Fallback |
|-------|---------------|----------|
| `purpose` | YAML `description` → manifest description → top SQL comment | Humanized filename |
| `grain` | Composite key tests → `GROUP BY` columns | Key-like unique columns |
| `primary_keys` | Composite key tests → unique + not_null tests → `GROUP BY` key columns | Empty |
| `derived_from` | `ref()` / `source()` → SQL table references | Empty |
| `filters_or_exclusions` | WHERE clauses matching filter terms → filter-related comments | Empty |
| `freshness_hints` | `materialized` config → time-related tokens in SQL/filenames | Empty |
| `alternatives` | Name similarity + dependency overlap + shared grain + filter differences | Empty |

### SQLite schema (storage.py)

Tables: `repos`, `scans`, `briefs`, `evidence`, `scan_files`, `briefs_fts` (FTS5 virtual table).

Key behaviors:
- Content-hash fingerprinting: re-scanning an unchanged repo reuses the existing scan.
- Retention: keeps the 3 most recent scans per repo; `gc` removes older ones.
- WAL mode for concurrent reads.

## Test fixtures

Ready-to-use repositories in `tests/fixtures/` for manual and automated testing:

| Fixture | Path | Project type | Tables |
|---------|------|-------------|--------|
| dbt_project | `tests/fixtures/dbt_project` | dbt | `mart.daily_active_users`, `mart.daily_active_users_all`, `mart.dim_users`, `staging.stg_events`, `kpi.weekly_growth` |
| sql_repo | `tests/fixtures/sql_repo` | sql | `staging.raw_orders`, `marts.orders_by_day`, `marts.orders_by_day_all`, `dashboards.weekly_orders` |
| monorepo_with_dbt | `tests/fixtures/monorepo_with_dbt` | dbt (nested) | `staging.stg_events`, `mart.daily_active_users` |
| multi_dbt_monorepo | `tests/fixtures/multi_dbt_monorepo` | error (ambiguous) | N/A -- used to test multi-project error |

### Quick fixture test

```bash
# Scan and query the dbt fixture
uv run tablebrief scan tests/fixtures/dbt_project
uv run tablebrief brief mart.daily_active_users --repo tests/fixtures/dbt_project --format json
uv run tablebrief compare mart.daily_active_users mart.daily_active_users_all \
  --repo tests/fixtures/dbt_project --format json
uv run tablebrief search "active users" --repo tests/fixtures/dbt_project --format json

# Scan and query the SQL fixture
uv run tablebrief scan tests/fixtures/sql_repo
uv run tablebrief brief marts.orders_by_day --repo tests/fixtures/sql_repo --format json
```

## Common agent tasks

### Adding a new heuristic

1. Add detection logic in `repository.py` (usually a new `_infer_*` or `_derive_*` function).
2. Wire it into `_build_brief()` and add evidence collection.
3. If it's a new field, add it to `TableBrief` in `models.py`.
4. Update renderers in `render.py` for both JSON and Markdown output.
5. Add tests in `tests/test_repository.py`.
6. Run `uv run ruff check . && uv run mypy src && uv run pytest`.

### Adding a new CLI command

1. Add the command function in `cli.py` with `@app.command()`.
2. Use the existing option types (`RepoOption`, `StoreOption`, `FormatOption`, etc.).
3. Follow the `try/except` + `_fail()` pattern for error handling.
4. Add tests in `tests/test_cli.py` using `typer.testing.CliRunner`.
5. Run quality checks.

### Adding a new MCP tool

1. Add the tool function in `mcp_server.py`.
2. Follow existing patterns (read from `CatalogStore`, return JSON-serializable dict).
3. Add tests in `tests/test_mcp_server.py`.
4. Run quality checks.

### Modifying Pydantic models

- All public data models live in `models.py`.
- Changes to `TableBrief` affect storage (the `payload_json` column stores the full model).
- Adding fields with defaults is backward-compatible with existing stored scans.
- Removing or renaming fields will break existing stored data.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `uv: command not found` | uv not on PATH | `source ~/.bashrc` or install: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `Repository has not been scanned` | No prior `scan` for this repo | Run `uv run tablebrief scan <path>` first |
| `Multiple dbt projects found` | Monorepo with >1 `dbt_project.yml` | Target a specific subdirectory: `uv run tablebrief scan path/to/specific/project` |
| `Table not found in catalog` | Wrong table name or repo not scanned | Check exact name with `uv run tablebrief export --repo <path> --format json` |
| `Table name is ambiguous` | Multiple tables share the short name | Use fully qualified name: `schema.model` |
| `The "mcp" package is required` | Missing optional dependency | `uv pip install "agent-table-brief[mcp]"` |
| Warning about `uv_build` version | Cosmetic version mismatch | Safe to ignore |

## Error output format

All CLI errors are written to stderr as structured JSON:

```json
{
  "code": "repo_not_scanned",
  "message": "Repository has not been scanned: /path/to/repo",
  "details": {"repo": "/path/to/repo"},
  "generated_at": "2026-03-07T00:00:00Z"
}
```

Error codes: `scan_failed`, `repo_not_scanned`, `repo_ambiguous`, `brief_not_found`,
`brief_ambiguous`, `compare_failed`, `search_failed`, `export_failed`, `repos_failed`,
`gc_failed`, `missing_dependency`.
