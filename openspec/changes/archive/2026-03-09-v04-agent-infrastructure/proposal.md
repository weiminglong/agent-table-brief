## Why

Coding agents writing SQL, ETL pipelines, and database code need more than table discovery — they need to understand columns, join paths, and usage patterns before they can write correct queries. Today tablebrief answers "what table should I use?" but not "how do I use this table correctly?" Additionally, agents only find tablebrief if someone manually configures MCP or tells the agent about it. There is no zero-config way for an agent entering a repo to discover that tablebrief is available, what it offers, or when to use it.

## What Changes

- **Column-level metadata**: Scan extracts column names, inferred types, and descriptions from schema.yml, manifest.json, and SQL DDL/CTAS statements. Each brief gains a `columns` field with per-column detail.
- **Join path inference**: Use `ref()`/`source()` calls, WHERE clause equi-joins, and YAML relationship tests to infer foreign-key-like join paths between tables. A new `joins` field on each brief surfaces how tables connect.
- **Full lineage DAG**: Expose multi-hop upstream and downstream lineage via a new `lineage` CLI command and MCP tool, not just the direct `derived_from`/`downstream_usage` lists.
- **Optional live DB enrichment**: `tablebrief scan --dsn <connection-string>` pulls real column types, descriptions, foreign key constraints, and row counts from `INFORMATION_SCHEMA` / `pg_catalog`. Falls back to local-only when no DSN is provided.
- **Agent discovery via `tablebrief init`**: Generate skill files (`.claude/skills/`), Cursor rules, and agent instructions so coding agents in the repo auto-discover tablebrief and use it before writing database code.
- **Query context**: Extract example query patterns from downstream models to show how a table is typically queried (joins used, columns selected, common filters).

## Capabilities

### New Capabilities
- `column-metadata`: Per-column name, inferred type, description, and sensitivity extracted from schema.yml, manifest, SQL, and optionally INFORMATION_SCHEMA.
- `join-paths`: Foreign-key-like relationships inferred from ref()/source(), WHERE equi-joins, and YAML tests, exposed per brief and as a cross-catalog graph.
- `lineage-dag`: Multi-hop upstream/downstream traversal beyond direct dependencies, exposed via CLI and MCP.
- `live-enrichment`: Optional database connection that pulls real schema, types, constraints, and statistics to enrich locally-scanned briefs.
- `agent-discovery`: `tablebrief init` command that generates skill files, editor rules, and agent instructions for zero-config agent integration.
- `query-context`: Example query patterns extracted from downstream SQL showing typical joins, filters, and column usage per table.

### Modified Capabilities
- `table-briefs`: Brief schema gains `columns`, `joins`, and `query_patterns` fields.
- `repo-scan`: Scanner gains column extraction, join inference, and optional DSN-based enrichment.
- `mcp-server`: New MCP tools for column lookup, join path discovery, and lineage traversal.

## Impact

- **Models** (`models.py`): `TableBrief` gains `columns: list[ColumnInfo]`, `joins: list[JoinPath]`, `query_patterns: list[QueryPattern]`. New Pydantic models for each. `LineageResult` model added.
- **Repository** (`repository.py`): New `_extract_columns`, `_infer_joins`, `_extract_query_patterns` functions. `_build_brief` wired to populate new fields. New optional `_enrich_from_db` path.
- **Storage** (`storage.py`): New `columns`, `joins` tables. `briefs` payload grows. FTS index extended with column names.
- **CLI** (`cli.py`): New `init` and `lineage` commands. `scan` gains `--dsn` option.
- **MCP** (`mcp_server.py`): New `get_columns`, `get_join_path`, `get_lineage` tools.
- **Render** (`render.py`): Updated renderers for columns, joins, query patterns.
- **Dependencies**: Optional `sqlalchemy` or `psycopg` for live DB connection. No new required dependencies.
- **Backwards compatibility**: All new fields default to empty lists. Existing JSON output shape is additive only. No breaking changes.
