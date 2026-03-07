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

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and use the OpenSpec
workflow in this repo for feature work.

## License

Released under the [MIT License](LICENSE).
