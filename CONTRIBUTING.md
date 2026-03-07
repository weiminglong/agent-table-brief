# Contributing

Thanks for contributing to `agent-table-brief`.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for environment and dependency
  management

## Setup

```bash
git clone https://github.com/weiminglong/agent-table-brief.git
cd agent-table-brief
uv sync --all-groups
```

Verify the install:

```bash
uv run tablebrief --help
uv run pytest
```

## Architecture

```
src/agent_table_brief/
├── cli.py          # Typer CLI: commands, options, error handling
├── models.py       # Pydantic schemas (TableBrief, Catalog, ScanResult, etc.)
├── repository.py   # Scanning engine: model discovery, SQL parsing, brief inference
├── storage.py      # SQLite store: CRUD, FTS5 search, fingerprinting, GC
├── render.py       # JSON and Markdown output formatting
└── mcp_server.py   # MCP server (optional dependency)
```

### Data flow

```
scan command
  │
  ▼
repository.scan_repository(path)
  ├── _resolve_scan_target()    → detect dbt vs plain SQL, find project root
  ├── _load_yaml_metadata()     → parse schema.yml / metadata YAML
  ├── _load_manifest_metadata() → parse target/manifest.json (if present)
  ├── _discover_model_files()   → find all .sql files
  ├── _discover_model()         → per-file: parse SQL, extract comments, refs, config
  ├── _build_name_lookup()      → short name → qualified name resolution
  ├── _build_downstream_map()   → reversed dependency graph
  └── _build_brief()            → per-model: infer purpose, grain, keys, etc.
  │
  ▼
Catalog (Pydantic model with list of TableBriefs)
  │
  ▼
storage.CatalogStore.store_scan()
  ├── fingerprint check (content-hash of all input files)
  ├── if unchanged → reuse existing scan
  └── if changed → INSERT into repos/scans/briefs/evidence/briefs_fts tables
  │
  ▼
ScanResult (JSON to stdout)
```

### Key design decisions

- **Heuristics over perfection**: the tool infers meaning from naming, comments, tests, and SQL
  structure. It prefers empty fields over speculative text.
- **Evidence-backed**: every inferred field links back to the source file and line range.
- **Idempotent scans**: a SHA-256 fingerprint of all input files prevents redundant re-scanning.
- **Structured errors**: CLI errors are JSON objects with `code`, `message`, and `details`.
- **Table naming**: tables use `schema.model` format. The schema comes from the directory path
  (e.g., `models/mart/foo.sql` → `mart.foo`). Config aliases and manifest metadata override this.

## Development Workflow

This repository uses OpenSpec as the source of truth for planned changes.

1. Create a change proposal:

   ```bash
   openspec new change <change-name>
   ```

2. Fill in the change artifacts under `openspec/changes/<change-name>/`.
3. Validate the spec work:

   ```bash
   openspec validate <change-name>
   ```

4. Implement the approved tasks.
5. Archive completed work:

   ```bash
   openspec archive <change-name> --yes
   ```

## Quality Checks

Run the full local check set before opening a pull request:

```bash
uv run ruff check .          # lint
uv run mypy src              # type check
uv run pytest                # unit/integration tests
openspec validate --specs    # spec validation (if applicable)
```

## Tests

Tests live in `tests/` and use pytest.

```bash
uv run pytest                # run all tests
uv run pytest -x             # stop on first failure
uv run pytest -k "test_scan" # run matching tests
```

### Test fixtures

Ready-made repository fixtures in `tests/fixtures/` cover the main project layouts:

| Fixture | Layout | What it tests |
|---------|--------|---------------|
| `dbt_project/` | Single dbt project with staging, mart, kpi layers | Core scanning: `ref()`, `schema.yml`, incremental config |
| `sql_repo/` | Plain SQL with `metadata/models.yml` | Non-dbt scanning: SQL table refs, YAML descriptions |
| `monorepo_with_dbt/` | Root SQL files + nested dbt project | Auto-detection of nested dbt project |
| `multi_dbt_monorepo/` | Two sibling dbt projects | Error handling for ambiguous repos |

These fixtures are also useful for manual CLI testing:

```bash
uv run tablebrief scan tests/fixtures/dbt_project
uv run tablebrief brief mart.daily_active_users --repo tests/fixtures/dbt_project --format json
uv run tablebrief scan tests/fixtures/sql_repo
uv run tablebrief brief marts.orders_by_day --repo tests/fixtures/sql_repo --format json
```

### Writing tests

- Place new tests in `tests/test_<module>.py`.
- Use the existing fixtures when possible. Add new fixtures under `tests/fixtures/` if your test
  requires a novel repo layout.
- Test both the happy path and error conditions.
- For CLI tests, use `typer.testing.CliRunner` (see `tests/test_cli.py` for examples).

## Code Style

- Line length: 100 characters (enforced by ruff).
- Formatting: ruff's default style.
- Lint rules: `E`, `F`, `I`, `B`, `UP`, `SIM` (see `pyproject.toml`).
- Type checking: strict mypy with Python 3.12 target.
- Prefer Pydantic models for any data that crosses module boundaries.
- Prefer `list[str]` / `dict[str, str]` over `List[str]` / `Dict[str, str]` (use modern syntax).

## Pull Requests

- Keep changes focused.
- Include tests when behavior changes.
- Update docs and OpenSpec specs when public behavior changes.
- Use clear, imperative commit titles.

## Reporting Bugs

Include:

- relevant SQL, YAML, or dbt model snippets
- the expected brief
- the actual brief
- why the current inference is misleading
