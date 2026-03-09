## 1. Column Metadata — Models and Extraction

- [x] 1.1 Add `ColumnInfo` Pydantic model to `models.py` with fields: name, type, description, tags, confidence
- [x] 1.2 Add `columns: list[ColumnInfo]` field to `TableBrief` (default empty list)
- [x] 1.3 Add `columns` table to SQLite schema in `storage.py` (scan_id, table_name, column_name, column_type, description, tags_json, confidence)
- [x] 1.4 Implement `_extract_columns_from_yaml` in `repository.py` — parse schema.yml column definitions
- [x] 1.5 Implement `_extract_columns_from_manifest` in `repository.py` — parse manifest.json column metadata
- [x] 1.6 Implement `_extract_columns_from_sql` in `repository.py` — use sqlglot to extract column names from final SELECT list
- [x] 1.7 Add PII sensitivity tagging — match column names against patterns (email, phone, ssn, address, ip_address) and dbt tags
- [x] 1.8 Wire column extraction into `_build_brief` with confidence scoring: YAML 0.95, manifest 0.90, SQL 0.65
- [x] 1.9 Store columns in both `payload_json` and dedicated `columns` table during `store_scan`
- [x] 1.10 Extend `briefs_fts` to index column names
- [x] 1.11 Update `render_brief_json` and `render_brief_markdown` to include columns section
- [x] 1.12 Add `field_confidence` entry for `columns`
- [x] 1.13 Add tests: column extraction from dbt fixture (YAML + SQL), PII tagging, FTS search by column name
- [x] 1.14 Run `ruff check . && mypy src && pytest`

## 2. Join Path Inference

- [x] 2.1 Add `JoinPath` Pydantic model to `models.py` with fields: to_table, on (list of column pairs), type, confidence
- [x] 2.2 Add `joins: list[JoinPath]` field to `TableBrief` (default empty list)
- [x] 2.3 Add `joins` table to SQLite schema (scan_id, source_table, target_table, on_json, join_type, confidence)
- [x] 2.4 Implement `_infer_joins_from_yaml` — extract from dbt `relationships` tests (confidence 0.95)
- [x] 2.5 Implement `_infer_joins_from_sql` — parse JOIN ON and WHERE equi-join clauses using sqlglot, correlate with ref()/source() (confidence 0.85 for JOIN ON, 0.60 for WHERE equi-join)
- [x] 2.6 Wire join inference into `_build_brief`, deduplicating across sources
- [x] 2.7 Store joins in both `payload_json` and dedicated `joins` table during `store_scan`
- [x] 2.8 Implement `find_join_path(store, table_a, table_b)` — BFS shortest path using recursive CTE over `joins` table
- [x] 2.9 Update renderers for joins section
- [x] 2.10 Add `field_confidence` entry for `joins`
- [x] 2.11 Add tests: join from relationship test, join from SQL JOIN ON, shortest path between two tables
- [x] 2.12 Run `ruff check . && mypy src && pytest`

## 3. Lineage DAG

- [x] 3.1 Add `LineageNode` and `LineageResult` Pydantic models to `models.py` (table_name, depth, direction)
- [x] 3.2 Implement `build_lineage(store, table, direction, max_depth)` in `repository.py` using recursive CTE over briefs' derived_from/downstream_usage
- [x] 3.3 Add `lineage` CLI command to `cli.py` with `--direction upstream|downstream|both`, `--depth N`, `--repo`, `--format` options
- [x] 3.4 Add `render_lineage_json` and `render_lineage_markdown` to `render.py`
- [x] 3.5 Add tests: upstream lineage with depth, downstream lineage, both directions, depth limit
- [x] 3.6 Run `ruff check . && mypy src && pytest`

## 4. Query Context

- [x] 4.1 Add `QueryPattern` Pydantic model to `models.py` with fields: source_model, columns_used, joins, filters
- [x] 4.2 Add `query_patterns: list[QueryPattern]` and `column_usage: dict[str, int]` to `TableBrief`
- [x] 4.3 Implement `_extract_query_patterns` in `repository.py` — for each table, parse downstream models' SQL to extract columns selected, joins used, and filters applied
- [x] 4.4 Implement `_build_column_usage` — aggregate column references across all downstream query patterns
- [x] 4.5 Wire into `_build_brief`, cap at 5 patterns per table
- [x] 4.6 Update renderers for query patterns and column usage
- [x] 4.7 Add tests: query pattern extraction from dbt fixture downstream model, column usage aggregation
- [x] 4.8 Run `ruff check . && mypy src && pytest`

## 5. Live Database Enrichment

- [x] 5.1 Add `sqlalchemy` as optional dependency in `pyproject.toml` under `[db]` extra
- [x] 5.2 Implement `_enrich_from_db(catalog, dsn)` in `repository.py` — connect via SQLAlchemy `inspect()`, pull column types, descriptions, FK constraints, row counts
- [x] 5.3 Add `--dsn` option to `scan` CLI command, support `env:VAR_NAME` syntax for reading from environment
- [x] 5.4 Merge live metadata into locally-scanned briefs: DB types override inferred types, DB FKs become high-confidence join paths, row counts added to freshness_hints
- [x] 5.5 Ensure DSN is never persisted in SQLite store
- [x] 5.6 Handle connection failure gracefully — warn and continue with local-only results
- [x] 5.7 Add tests: enrichment with mock SQLAlchemy inspector, connection failure fallback, DSN not in store
- [x] 5.8 Run `ruff check . && mypy src && pytest`

## 6. MCP Server Extensions

- [x] 6.1 Add `get_columns` MCP tool — returns column list for a table with names, types, descriptions, tags
- [x] 6.2 Add `get_join_path` MCP tool — returns shortest join path between two tables
- [x] 6.3 Add `get_lineage` MCP tool — returns multi-hop lineage with direction and depth params
- [x] 6.4 Update `get_brief` to include columns, joins, and query_patterns in response
- [x] 6.5 Add tests for new MCP tools
- [x] 6.6 Run `ruff check . && mypy src && pytest`

## 7. Agent Discovery — `tablebrief init`

- [x] 7.1 Implement `init` CLI command in `cli.py` with `--scan`, `--agent` options
- [x] 7.2 Implement agent detection — check for `.claude/`, `.cursor/`, `.windsurf/` directories
- [x] 7.3 Generate Claude Code skill file at `.claude/skills/tablebrief/SKILL.md` — instructions for when/how to use tablebrief before writing SQL, ETL, or database code
- [x] 7.4 Generate Cursor rules file at `.cursor/rules/tablebrief.md` and MCP config at `.cursor/mcp.json`
- [x] 7.5 Append "Table Context" section to AGENTS.md if it exists and doesn't already have the section
- [x] 7.6 Add version marker to generated files for staleness detection on re-run
- [x] 7.7 Make `init` idempotent — update existing files without duplicating content
- [x] 7.8 Add tests: init generates expected files, idempotent re-run, AGENTS.md append
- [x] 7.9 Run `ruff check . && mypy src && pytest`

## 8. Integration and Quality

- [x] 8.1 Update AGENTS.md with new commands (lineage, init), new MCP tools, and updated brief schema
- [x] 8.2 Update test fixtures to include column definitions in schema.yml and relationship tests
- [x] 8.3 Run full quality suite: `ruff check . && mypy src && pytest`
- [x] 8.4 Verify backwards compatibility: scan existing fixture, confirm old brief fields unchanged, new fields default to empty
