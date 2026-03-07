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

## Quickstart

Get from zero to your first table brief in under a minute.

**Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# 1. Clone and install
git clone https://github.com/weiminglong/agent-table-brief.git
cd agent-table-brief
uv sync --all-groups

# 2. Scan the included demo project
uv run tablebrief scan tests/fixtures/dbt_project

# 3. View a brief
uv run tablebrief brief mart.daily_active_users \
  --repo tests/fixtures/dbt_project --format json

# 4. Compare two similar tables
uv run tablebrief compare mart.daily_active_users mart.daily_active_users_all \
  --repo tests/fixtures/dbt_project --format json

# 5. Search the catalog
uv run tablebrief search "active users" \
  --repo tests/fixtures/dbt_project --format json

# 6. Export everything as Markdown
uv run tablebrief export \
  --repo tests/fixtures/dbt_project --format markdown
```

## Features

`tablebrief` scans dbt projects, plain SQL repositories, and YAML metadata files. It uses
comments, naming conventions, lineage, tests, and filter heuristics to produce briefs containing:

- purpose, grain, and likely keys
- upstream dependencies and downstream usage
- freshness hints and common exclusions/filters
- likely alternate tables with similarity scoring
- per-field confidence scores
- evidence links back to files and line ranges

Beyond scanning, `tablebrief` also provides:

- **compare** -- side-by-side structured diff of two or more tables
- **search** -- full-text search over the catalog using SQLite FTS5
- **MCP server** -- expose the catalog to AI editors and agents via the Model Context Protocol

## How It Works

```
your repo                tablebrief                  output
─────────                ──────────                  ──────
.sql files ──┐
.yml files ──┤  scan ──► SQLite store ──► brief (JSON/Markdown)
dbt config ──┤                       ──► compare
manifest   ──┘                       ──► search (FTS5)
                                     ──► export (full catalog)
                                     ──► MCP server (for AI editors)
```

1. **Scan** discovers SQL models (`.sql` files) and YAML metadata (`.yml` / `.yaml`) in a dbt or
   plain SQL project. It parses SQL with [sqlglot](https://github.com/tobymao/sqlglot), reads
   dbt `ref()` / `source()` calls, extracts comments, inspects `schema.yml` tests, and reads
   `target/manifest.json` when available.
2. **Build briefs** for each discovered table: purpose (from descriptions, comments, or filename),
   grain (from `GROUP BY`, composite key tests, or unique constraints), primary keys, upstream
   dependencies, downstream consumers, freshness hints, filters/exclusions, and similar
   alternative tables.
3. **Store** the resulting catalog in a local SQLite database with content-hash deduplication so
   re-scanning unchanged repos is instant.
4. **Query** the catalog via CLI commands, JSON/Markdown output, or the MCP server.

### Table naming

Tables are named as `schema.model` where:

- **dbt projects**: schema comes from the directory under `models/` (e.g.,
  `models/mart/daily_active_users.sql` becomes `mart.daily_active_users`).
  Aliases and schemas from `config()` or `manifest.json` take priority.
- **plain SQL projects**: schema comes from the parent directory of the `.sql` file.

### Confidence scores

Every brief includes a `confidence` score (0.0 -- 0.99) and per-field `field_confidence` scores.
These indicate how much evidence backed each inference:

| Score range | Meaning |
|-------------|---------|
| 0.90 -- 0.99 | Strong evidence (explicit YAML description, composite key test) |
| 0.60 -- 0.89 | Moderate evidence (top comment, GROUP BY columns, schema tests) |
| 0.40 -- 0.59 | Weak evidence (filename heuristic only) |
| 0.00 | No evidence found for this field |

## Install

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and sync
git clone https://github.com/weiminglong/agent-table-brief.git
cd agent-table-brief
uv sync --all-groups

# Verify
uv run tablebrief --help
```

## CLI Reference

### `scan` -- ingest a repository

```bash
uv run tablebrief scan path/to/repo
uv run tablebrief scan path/to/repo --project-type dbt   # force dbt mode
uv run tablebrief scan path/to/repo --project-type sql   # force plain SQL mode
```

In `auto` mode (the default), `tablebrief` detects whether the repo is dbt or plain SQL. If the
directory contains exactly one nested `dbt_project.yml`, it auto-selects that project. If
multiple are found, it raises an error asking you to target one subdirectory.

### `brief` -- get one table's brief

```bash
uv run tablebrief brief mart.daily_active_users --repo path/to/repo --format json
uv run tablebrief brief daily_active_users --repo path/to/repo   # short name works if unambiguous
```

### `compare` -- diff two or more tables

```bash
uv run tablebrief compare mart.daily_active_users mart.daily_active_users_all \
  --repo path/to/repo --format json
```

Returns a structured diff showing only the fields that diverge between tables.

### `search` -- full-text search

```bash
uv run tablebrief search "daily active users" --repo path/to/repo --format json --limit 10
```

Uses SQLite FTS5 to search across table names, purposes, grain, filters, and alternatives.

### `export` -- dump the full catalog

```bash
uv run tablebrief export --repo path/to/repo --format markdown --output briefs.md
uv run tablebrief export --repo path/to/repo --format json
```

### `repos` -- list scanned repositories

```bash
uv run tablebrief repos
```

### `gc` / `vacuum` -- maintenance

```bash
uv run tablebrief gc       # remove old scans (keeps 3 per repo)
uv run tablebrief vacuum   # reclaim SQLite disk space
```

### Global options

| Option | Description |
|--------|-------------|
| `--repo PATH` | Path to the scanned repository (defaults to `.`) |
| `--store PATH` | Path to the SQLite store file (overrides default) |
| `--format json\|markdown` | Output format (defaults to `json`) |
| `--output PATH` | Write output to a file instead of stdout |

All output is structured JSON by default, making it easy for scripts and agents to consume.
Errors are also structured JSON (written to stderr) with a `code`, `message`, and `details` fields.

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

### Available MCP Tools

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

Scanning is **idempotent**: if the repo files haven't changed since the last scan (based on a
content hash of all input files), the existing catalog is reused and the response includes
`"reused": true`.

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
  "field_confidence": {
    "purpose": 0.95,
    "grain": 0.95,
    "primary_keys": 0.95,
    "derived_from": 0.95,
    "filters_or_exclusions": 0.9,
    "freshness_hints": 0.9,
    "downstream_usage": 0.9,
    "alternatives": 0.8
  },
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

## Supported Repository Layouts

| Layout | How tablebrief detects it | What gets scanned |
|--------|--------------------------|-------------------|
| **Single dbt project** | `dbt_project.yml` at root | `models/**/*.sql` + `*.yml` metadata |
| **Monorepo with nested dbt** | Exactly one `dbt_project.yml` in a subdirectory | That subdirectory's `models/**/*.sql` |
| **Multi-dbt monorepo** | Multiple `dbt_project.yml` files | Error -- scan one subdirectory directly |
| **Plain SQL repo** | No `dbt_project.yml`, but `.sql` files exist | All `**/*.sql` + `*.yml` metadata |

Use `--project-type dbt` or `--project-type sql` to skip auto-detection.

## Project Architecture

```
src/agent_table_brief/
├── cli.py          # Typer CLI commands and option definitions
├── models.py       # Pydantic schemas (TableBrief, Catalog, ScanResult, etc.)
├── repository.py   # Scanning logic: discovery, SQL parsing, heuristic inference
├── storage.py      # SQLite store: read/write scans, FTS5 search, GC
├── render.py       # JSON and Markdown output formatting
└── mcp_server.py   # MCP server exposing catalog as AI-editor tools
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
uv run ruff check .          # lint
uv run mypy src              # type check
uv run pytest                # tests
openspec validate --specs    # spec validation
```

## Limitations

`agent-table-brief` does not try to:

- replace warehouse documentation tools
- guarantee true business meaning
- infer every metric definition
- execute SQL
- resolve every ambiguity automatically

It is a context extraction tool, not a warehouse agent.

## Roadmap

- v0.1: repo scan, dbt model discovery, SQLite-backed local store, brief/export *(shipped)*
- v0.2: better alternatives, compare command, stronger evidence mapping, confidence scoring *(shipped)*
- v0.3: full-text search, MCP server *(shipped)*, editor integrations, optional warehouse metadata fusion

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and use the OpenSpec
workflow in this repo for feature work.

## License

Released under the [MIT License](LICENSE).
