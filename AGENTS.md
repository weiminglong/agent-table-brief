# AGENTS.md

## Cursor Cloud specific instructions

This is a Python CLI tool (`tablebrief`) managed by **uv**. No external services, databases, or Docker containers are needed — it is fully local-first with an embedded SQLite store.

### Running quality checks

Standard commands from `README.md` and `CONTRIBUTING.md`:

```bash
uv run ruff check .      # lint
uv run mypy src           # type check
uv run pytest             # tests
```

### Running the CLI

```bash
uv run tablebrief --help
uv run tablebrief scan <path-to-repo>
uv run tablebrief brief <table-name> --repo <path> --format json
uv run tablebrief compare <tableA> <tableB> --repo <path> --format json
uv run tablebrief search "<query>" --repo <path> --format json --limit 10
uv run tablebrief export --repo <path> --format markdown
uv run tablebrief serve                        # start MCP server (requires mcp extra)
```

Test fixtures at `tests/fixtures/` (dbt_project, sql_repo, monorepo_with_dbt, multi_dbt_monorepo) are useful for manual CLI testing.

### Non-obvious notes

- The `uv_build` version constraint in `pyproject.toml` (`>=0.9.26,<0.10.0`) may emit a warning with newer `uv` versions. This is cosmetic and does not affect functionality.
- The SQLite store location defaults to `~/.local/state/tablebrief/store.db` on Linux. Override with `--store <path>` or `TABLEBRIEF_HOME` env var for isolated testing.
- `uv` must be on `PATH` — it is installed to `~/.local/bin` via `astral.sh/uv/install.sh` and persisted in `~/.bashrc`.
