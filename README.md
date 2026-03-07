# agent-table-brief

Turn analytics codebases into compact table briefs that coding agents can actually use.

`agent-table-brief` is a local-first CLI toolkit that scans a dbt or SQL repository and extracts
table-level context like purpose, grain, keys, exclusions, dependencies, and likely alternatives.
Its primary CLI command, `tablebrief`, is designed for coding agents that need better table
understanding before they generate SQL. Runtime state lives in a local SQLite store, with JSON and
Markdown exports available on demand.

## Why

In most analytics repos, the hard part is not SQL syntax. The hard part is choosing the right
table.

Two models can have nearly identical schemas but very different meanings:

- one excludes internal users and the other does not
- one is session-grain and the other is user-day grain
- one is incremental and fresh, the other is historical
- one is an aggregate intended for dashboards, the other is a staging model

That context often lives in code, comments, tests, YAML, naming patterns, and lineage, not just
schemas. `agent-table-brief` extracts that context into a local catalog that humans and coding
agents can reuse.

## MVP Surface

`tablebrief` currently supports:

- dbt projects
- plain SQL repositories
- YAML metadata files using dbt-style `models:` or `tables:` entries
- comments, naming conventions, lineage, tests, and filter heuristics

It produces:

- purpose
- grain
- likely keys
- upstream dependencies
- downstream usage
- freshness hints
- common exclusions and filters
- likely alternate tables
- confidence score
- evidence links back to files and lines

## Install

```bash
uv sync --all-groups
```

Run the CLI through `uv` during development:

```bash
uv run tablebrief --help
```

## Usage

Scan a repository into the local store:

```bash
uv run tablebrief scan path/to/repo
```

In auto mode, `tablebrief` will scan a nested dbt project if the provided directory contains
exactly one `dbt_project.yml`. If multiple nested dbt projects are present, it raises an error and
asks you to target one subdirectory directly.

Generate a brief for one table:

```bash
uv run tablebrief brief mart.daily_active_users --repo path/to/repo --format json
```

Export the active stored catalog:

```bash
uv run tablebrief export --repo path/to/repo --format markdown --output briefs.md
```

List scanned repositories:

```bash
uv run tablebrief repos
```

Maintenance commands:

```bash
uv run tablebrief gc
uv run tablebrief vacuum
```

## MCP Server

`tablebrief` includes an optional [Model Context Protocol](https://modelcontextprotocol.io)
server so AI editors and agents can query table briefs directly.

Install the MCP extra:

```bash
uv pip install "agent-table-brief[mcp]"
```

Start the server:

```bash
uv run tablebrief serve
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "tablebrief": {
      "command": "uv",
      "args": ["run", "tablebrief", "serve"]
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tablebrief": {
      "command": "uv",
      "args": ["run", "tablebrief", "serve"]
    }
  }
}
```

### Available Tools

| Tool | Description |
|------|-------------|
| `search_tables` | Search tables by keyword across purpose, grain, filters, and names |
| `get_brief` | Get the full brief for a specific table |
| `compare_tables` | Compare two or more tables side-by-side |
| `list_tables` | List all tables in a scanned repository |
| `list_repos` | List all scanned repositories |

## Storage

By default, `tablebrief` stores scans in a local SQLite database at:

- `$TABLEBRIEF_HOME/store.db` when `TABLEBRIEF_HOME` is set
- macOS: `~/Library/Application Support/tablebrief/store.db`
- Linux: `$XDG_STATE_HOME/tablebrief/store.db` or `~/.local/state/tablebrief/store.db`
- Windows: `%LOCALAPPDATA%\\tablebrief\\store.db`

Override the database location per command with `--store <path>`.

## Example Brief

```json
{
  "table": "mart.daily_active_users",
  "purpose": "Daily active users by product surface",
  "grain": "activity_date x user_id",
  "primary_keys": ["activity_date", "user_id"],
  "derived_from": ["stg.events", "dim.users"],
  "filters_or_exclusions": ["excludes employees", "logged-in users only"],
  "freshness_hints": ["incremental model", "likely daily batch"],
  "downstream_usage": ["kpi.weekly_growth", "retention_dashboard"],
  "alternatives": ["mart.daily_active_users_all", "mart.session_users"],
  "confidence": 0.73,
  "evidence": [
    {
      "file": "models/mart/daily_active_users.sql",
      "start_line": 1,
      "end_line": 14,
      "kind": "sql"
    }
  ]
}
```

## Example Scan Result

```json
{
  "repo_key": "d3683f03e2bb42b259baecf27e52042d9faeb8abe60caa45e79ae9d974180f5a",
  "repo_root": "/path/to/repo",
  "effective_root": "/path/to/repo/dbt_clickhouse",
  "project_type": "dbt",
  "scan_id": 1,
  "status": "complete",
  "reused": false,
  "brief_count": 914,
  "generated_at": "2026-03-07T04:07:09.663114Z"
}
```

## OpenSpec Workflow

This repo uses OpenSpec as the source of truth for future planning.

1. Start work with a change proposal:

   ```bash
   openspec new change <change-name>
   ```

2. Add or refine:
   - `openspec/changes/<change-name>/proposal.md`
   - `openspec/changes/<change-name>/design.md`
   - `openspec/changes/<change-name>/tasks.md`
   - any delta specs under `openspec/changes/<change-name>/specs/`

3. Validate before implementation:

   ```bash
   openspec validate <change-name>
   ```

4. Implement the agreed tasks.

5. Archive completed work back into source-of-truth specs:

   ```bash
   openspec archive <change-name> --yes
   ```

Baseline source-of-truth specs live under `openspec/specs/`.

## Development

Quality checks:

```bash
uv run ruff check .
uv run mypy src
uv run pytest
openspec validate --specs
```

## Limitations

At least in v0.1, `agent-table-brief` does not try to:

- replace warehouse documentation tools
- guarantee true business meaning
- infer every metric definition
- execute SQL
- resolve every ambiguity automatically

It is a context extraction tool, not a warehouse agent.

## Roadmap

- v0.1: repo scan, dbt model discovery, SQLite-backed local store, brief/export
- v0.2: better alternatives, compare command, stronger evidence mapping, confidence scoring
- v0.3: semantic search, MCP server, editor integrations, optional warehouse metadata fusion

## v0.3 Implementation Plan

v0.3 turns `tablebrief` from a CLI-only tool into an always-available context source for coding
agents and editors. The four features ship in dependency order across three phases.

### Phase 1 — Search (`tablebrief search`)

Add full-text and keyword search over the stored catalog so users and agents can find tables by
intent rather than exact name.

**Approach:** Use SQLite FTS5 (built-in, zero new dependencies) over the brief fields already
stored in the `briefs` table. A new virtual table indexes `table_name`, `purpose`, `grain`,
`filters_or_exclusions`, and `alternatives`. Results are ranked by FTS5 `bm25()` and optionally
filtered by repo.

| Task | Module | Detail |
|------|--------|--------|
| 1.1 FTS5 schema migration | `storage.py` | Add `briefs_fts` virtual table (`CREATE VIRTUAL TABLE IF NOT EXISTS briefs_fts USING fts5(...)`) in `_initialize`. Populate from `briefs` rows at scan time. |
| 1.2 Search storage method | `storage.py` | `CatalogStore.search(query, repo_path, limit)` → runs `SELECT ... FROM briefs_fts WHERE briefs_fts MATCH ? ORDER BY bm25(briefs_fts) LIMIT ?`, joins back to `briefs` to load full `TableBrief` payloads. |
| 1.3 `SearchResult` model | `models.py` | New `SearchResult(query: str, results: list[SearchHit])` and `SearchHit(table: str, rank: float, brief: TableBrief)` Pydantic models. |
| 1.4 `search` CLI command | `cli.py` | `tablebrief search <query> [--repo] [--store] [--format json\|markdown] [--limit 10]`. |
| 1.5 Markdown/JSON renderers | `render.py` | `render_search_json`, `render_search_markdown`. |
| 1.6 Tests | `tests/` | FTS indexing round-trip, search ranking with dbt fixture, CLI smoke test, no-results case. |

**Acceptance:** `tablebrief search "daily active users" --repo tests/fixtures/dbt_project`
returns ranked briefs with tables whose purpose, grain, or name match the query.

---

### Phase 2 — MCP Server (`tablebrief serve`)

Expose the catalog over the [Model Context Protocol](https://modelcontextprotocol.io) so AI
editors and agents can query table briefs without shelling out to the CLI.

**Approach:** Add a new `mcp_server.py` module using the `mcp` Python SDK. The server runs as a
stdio-based MCP server (started via `tablebrief serve` or directly as
`python -m agent_table_brief.mcp_server`). It exposes the existing catalog operations as MCP
tools.

| Task | Module | Detail |
|------|--------|--------|
| 2.1 Add `mcp` dependency | `pyproject.toml` | Add `mcp>=1.0.0` as an optional dependency group (`[project.optional-dependencies] mcp = ["mcp>=1.0.0"]`). |
| 2.2 MCP tool definitions | `mcp_server.py` | Define MCP tools: `search_tables(query, repo?, limit?)`, `get_brief(table, repo?)`, `compare_tables(tables[], repo?)`, `list_tables(repo?)`, `list_repos()`. Each tool delegates to existing `CatalogStore` / `repository` methods. |
| 2.3 MCP resource: catalog | `mcp_server.py` | Expose `tablebrief://catalog/{repo_key}` as an MCP resource returning the full catalog JSON. |
| 2.4 `serve` CLI command | `cli.py` | `tablebrief serve [--store <path>]` starts the MCP stdio server. Lazy-imports `mcp_server` so the `mcp` dependency is only required when serving. |
| 2.5 Server configuration doc | `README.md` | Document MCP server config for Claude Desktop, Cursor, and other MCP clients (JSON snippet for `mcpServers`). |
| 2.6 Tests | `tests/` | Unit tests for each tool handler using an in-memory store. Integration test that starts the server, sends a JSON-RPC `tools/call`, and validates the response. |

**MCP tool signatures (JSON-Schema input):**

```
search_tables   { query: string, repo?: string, limit?: int }
get_brief       { table: string, repo?: string }
compare_tables  { tables: string[], repo?: string }
list_tables     { repo?: string }
list_repos      { }
```

**Acceptance:** An MCP client can connect to `tablebrief serve`, call `search_tables` with a
natural language query, and receive ranked brief results.

---

### Phase 3a — Editor Integrations

With the MCP server in place, editor integration is mostly configuration. This phase adds
ready-to-use config snippets and a lightweight VS Code extension.

| Task | Detail |
|------|--------|
| 3.1 MCP client config examples | Add config snippets for Cursor (`.cursor/mcp.json`), Claude Desktop (`claude_desktop_config.json`), and Continue (`config.json`) showing how to connect to `tablebrief serve`. |
| 3.2 VS Code extension scaffold | Create `editors/vscode/` with a minimal VS Code extension that: (a) starts `tablebrief serve` as a child process, (b) adds a "Table Brief: Search" command palette entry, (c) shows brief results in a webview panel. Uses the MCP TypeScript SDK or direct JSON-RPC over stdio. |
| 3.3 Hover provider (stretch) | In the VS Code extension, register a hover provider for `.sql` files. When the cursor is over a `ref('model_name')` or `FROM schema.table`, call `get_brief` and show purpose, grain, and confidence in a hover tooltip. |

**Acceptance:** A user can install the VS Code extension, open a dbt project, and see table brief
hover tooltips over `ref()` calls.

---

### Phase 3b — Optional Warehouse Metadata Fusion

Allow enriching briefs with live metadata from a connected data warehouse. This is additive —
`tablebrief` remains fully functional without warehouse access.

**Approach:** A new `warehouse.py` module with an adapter interface and concrete adapters for
common warehouses. Warehouse metadata is merged into briefs at scan time when a connection is
configured.

| Task | Module | Detail |
|------|--------|--------|
| 4.1 Adapter interface | `warehouse.py` | `WarehouseAdapter` protocol with methods: `get_columns(table) → list[ColumnInfo]`, `get_row_count(table) → int?`, `get_freshness(table) → datetime?`. |
| 4.2 Snowflake adapter | `warehouse.py` | Adapter using `snowflake-connector-python` (optional dep). Reads `INFORMATION_SCHEMA.COLUMNS`, `TABLE_STORAGE_METRICS`, and `INFORMATION_SCHEMA.TABLES.LAST_ALTERED`. |
| 4.3 BigQuery adapter | `warehouse.py` | Adapter using `google-cloud-bigquery` (optional dep). Reads table metadata and schema from the BigQuery API. |
| 4.4 PostgreSQL adapter | `warehouse.py` | Adapter using `psycopg` (optional dep). Reads `information_schema.columns` and `pg_stat_user_tables`. |
| 4.5 Fusion logic | `repository.py` | New `_enrich_brief_with_warehouse(brief, adapter)` function called at the end of `_build_brief` when an adapter is available. Adds `column_types`, `row_count`, and `warehouse_freshness` to the brief. |
| 4.6 `TableBrief` schema additions | `models.py` | Add optional fields: `column_types: dict[str, str]`, `row_count: int \| None`, `warehouse_freshness: datetime \| None`. Default to `None`/empty so non-warehouse scans are unchanged. |
| 4.7 CLI integration | `cli.py` | Add `--warehouse <connection-string>` option to `scan`. Parse the scheme (`snowflake://`, `bigquery://`, `postgresql://`) to select the adapter. |
| 4.8 Optional dependency groups | `pyproject.toml` | `[project.optional-dependencies]` entries: `snowflake`, `bigquery`, `postgres`. |
| 4.9 Tests | `tests/` | Unit tests with mock adapters. Integration test with SQLite (as a stand-in) verifying the fusion path. |

**Acceptance:** `tablebrief scan path/to/repo --warehouse snowflake://...` produces briefs with
`column_types`, `row_count`, and `warehouse_freshness` populated from the live warehouse.

---

### Sequencing and Dependencies

```
Phase 1 (search)  ─────►  Phase 2 (MCP server)  ─────►  Phase 3a (editors)
                                    │
                                    └──────────────────►  Phase 3b (warehouse fusion)
```

- **Phase 1** is a prerequisite for Phase 2 because the MCP server exposes `search_tables`.
- **Phase 2** is a prerequisite for Phase 3a because editor integrations consume the MCP server.
- **Phase 3b** is independent of Phase 3a and can be built in parallel after Phase 2.

### New Dependencies

| Dependency | Phase | Required | Notes |
|------------|-------|----------|-------|
| *(none)* | 1 | — | FTS5 is built into SQLite / Python stdlib |
| `mcp` | 2 | optional | Only needed when running `tablebrief serve` |
| `snowflake-connector-python` | 3b | optional | Only for Snowflake warehouse fusion |
| `google-cloud-bigquery` | 3b | optional | Only for BigQuery warehouse fusion |
| `psycopg` | 3b | optional | Only for PostgreSQL warehouse fusion |

### Version Bump

Bump `version` in `pyproject.toml` and `__version__` in `__init__.py` to `0.3.0` after Phase 2
is complete and the MCP server is functional. Phase 3a and 3b can ship as patch releases
(`0.3.1`, `0.3.2`).

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and use the OpenSpec
workflow in this repo for feature work.

## License

Released under the [MIT License](LICENSE).
