## Context

Tablebrief v0.1–v0.3 provides table-level briefs: purpose, grain, keys, dependencies, filters, alternatives, and confidence. Agents can discover tables and compare them, but cannot inspect columns, understand join relationships, traverse lineage, or learn from query patterns. The system is local-first with no database connection, and agents only discover tablebrief if someone manually configures MCP or mentions it.

The codebase is a single Python package (`agent_table_brief`) with 6 modules totaling ~2,500 lines. All data lives in a local SQLite store with FTS5 search.

## Goals / Non-Goals

**Goals:**
- Add column-level metadata (name, type, description, sensitivity) to each brief
- Infer join paths between tables from SQL, refs, and YAML tests
- Expose multi-hop lineage via CLI and MCP
- Support optional live database enrichment via `--dsn`
- Generate agent integration files via `tablebrief init`
- Extract query patterns from downstream models
- Keep all new fields backward-compatible (default to empty)

**Non-Goals:**
- Building a full data catalog (Datahub, Amundsen-style)
- Semantic/LLM-based analysis of column meaning
- Real-time warehouse monitoring or alerting
- Supporting non-SQL databases (MongoDB, etc.)
- Query execution or performance benchmarking
- Column-level lineage (tracking transformations per column)

## Decisions

### 1. Column metadata model

**Choice:** Add `ColumnInfo` Pydantic model with fields: `name: str`, `type: str | None`, `description: str | None`, `tags: list[str]`, `confidence: float`. Store as part of the brief's `payload_json` plus a dedicated `columns` table for FTS indexing.

**Rationale:** Keeping columns in the brief payload maintains the single-JSON-blob simplicity. A separate `columns` table enables searching by column name ("which table has a user_id column?") without parsing JSON. Both are needed.

**Alternative considered:** Separate `columns` table only, no embedding in brief. Rejected because it breaks the "one brief = one JSON" contract that agents rely on.

### 2. Join path representation

**Choice:** Add `JoinPath` Pydantic model: `to_table: str`, `on: list[tuple[str, str]]` (source_col, target_col pairs), `type: str | None` (inner/left/right/full), `confidence: float`. Store in brief payload as `joins: list[JoinPath]` and in a dedicated `joins` table for graph queries.

**Rationale:** Joins are properties of the relationship between tables, but most useful when attached to a specific brief ("how does this table connect to others?"). The dedicated table enables shortest-path queries across the full catalog.

**Alternative considered:** Graph database (NetworkX in-memory). Rejected as over-engineered — SQLite recursive CTEs handle shortest-path queries for catalogs of typical size (< 10k tables).

### 3. Join inference sources (priority order)

**Choice:** Infer joins from three sources with decreasing confidence:
1. YAML `relationships` tests → confidence 0.95
2. `ref()`/`source()` + JOIN ON clause → confidence 0.85
3. WHERE equi-join on identically-named columns → confidence 0.60

**Rationale:** Relationship tests are explicit declarations of foreign keys. ref() + JOIN is strong structural evidence. WHERE equi-joins on same-named columns are heuristic but useful — the matching column name provides signal.

### 4. Lineage via recursive CTE

**Choice:** Implement lineage traversal as a SQLite recursive CTE over the `derived_from` / `downstream_usage` data already stored in briefs, rather than building an in-memory graph.

**Rationale:** The data is already in SQLite. Recursive CTEs are standard, efficient for the expected catalog size, and don't require new dependencies. The `--depth` limit maps directly to the CTE recursion limit.

**Alternative considered:** Build a NetworkX DiGraph at query time. Rejected — adds a dependency for something SQLite handles natively.

### 5. Live enrichment architecture

**Choice:** Add an optional `_enrich_from_db(catalog, dsn)` post-processing step that runs after local scanning. Uses SQLAlchemy `inspect()` for database-agnostic schema introspection. Connection string is never persisted.

**Rationale:** Post-processing keeps the enrichment cleanly separated from the scan pipeline. SQLAlchemy's `inspect()` provides a uniform API across Postgres, MySQL, Snowflake, BigQuery (via dialect), and DuckDB.

**Alternative considered:** Direct `psycopg` for Postgres only. Rejected — too narrow. SQLAlchemy's inspection API covers more databases with minimal code.

**Dependency:** `sqlalchemy` added as an optional extra (`agent-table-brief[db]`). No new required dependencies.

### 6. Agent discovery via `init`

**Choice:** `tablebrief init` detects which AI tools are present (Claude Code, Cursor, Windsurf) by checking for `.claude/`, `.cursor/`, `.windsurf/` directories, then generates appropriate integration files:
- Claude Code: `.claude/skills/tablebrief/SKILL.md`
- Cursor: `.cursor/rules/tablebrief.md` + `.cursor/mcp.json`
- AGENTS.md: append section if file exists

**Rationale:** Follow the OpenSpec distribution pattern — generate tool-specific files that agents auto-detect. The skill file teaches the agent *when* and *how* to use tablebrief, not just that it exists.

**Alternative considered:** Only provide MCP and let agents figure it out. Rejected — agents need explicit instructions about *when* to reach for tablebrief (before writing SQL, when choosing tables, when building ETL).

### 7. Query pattern extraction

**Choice:** During scan, for each table T, examine all downstream models that reference T. Parse each downstream model's SQL and extract: columns selected from T, join conditions involving T, and WHERE filters on T's columns. Store as `query_patterns: list[QueryPattern]` on T's brief, capped at 5 patterns.

**Rationale:** Downstream models are the best signal for "how is this table actually used?" — they show real column selections, join patterns, and filter idioms. Capping at 5 prevents bloat.

**Alternative considered:** Store raw SQL snippets. Rejected — structured extraction is more useful for agents and more compact.

### 8. Storage schema changes

**Choice:** Add two new SQLite tables:
```sql
columns (scan_id, table_name, column_name, column_type, description, tags_json, confidence)
joins (scan_id, source_table, target_table, on_json, join_type, confidence)
```
Extend `briefs_fts` to include column names. Brief `payload_json` continues to hold the full serialized brief including the new fields.

**Rationale:** Dedicated tables enable column-name search and join-graph queries without JSON parsing. The brief payload remains the canonical source for full brief retrieval.

### 9. Implementation phasing

**Choice:** Implement in 4 phases within this change:
1. **Column metadata + storage** — foundation that everything else builds on
2. **Join paths + lineage** — relationship layer
3. **Query context + live enrichment** — richer signals
4. **Agent discovery (init)** — distribution layer

**Rationale:** Each phase produces independently useful output. Columns must come first because joins and query patterns reference column names. Agent discovery comes last because the value of init depends on the richness of the catalog it exposes.

## Risks / Trade-offs

- **[Brief size growth]** → Adding columns, joins, and query patterns could make briefs significantly larger. Mitigation: cap columns at 200, joins at 50, query patterns at 5 per table. Agents can request columns separately via `get_columns` for wide tables.
- **[SQLAlchemy dependency weight]** → SQLAlchemy is a heavy optional dependency. Mitigation: keep it in the `[db]` extra, never import it unless `--dsn` is used. Consider supporting a lighter alternative (e.g., `connectorx`) in the future.
- **[Join inference false positives]** → WHERE equi-joins on common column names (id, name, type) may produce false joins. Mitigation: lower confidence (0.60) for heuristic joins; require column name match, not just position.
- **[Credential exposure]** → DSN strings contain credentials. Mitigation: never persist DSN in SQLite; support `env:VAR_NAME` syntax; document security implications.
- **[Init file staleness]** → Generated skill files may become outdated as tablebrief evolves. Mitigation: include a version marker in generated files; `tablebrief init` can detect and update stale files.

## Migration Plan

1. Storage schema changes are additive (new tables, new FTS columns). Existing stores continue to work — new tables are created on first access.
2. Brief `payload_json` gains new fields with defaults. Existing stored briefs deserialize correctly with empty columns/joins/query_patterns.
3. No breaking changes to CLI output shape. New fields appear alongside existing ones.
4. `[db]` extra is optional. Users who don't need live enrichment don't install SQLAlchemy.

## Open Questions

1. **Column limit per table** — Is 200 columns the right cap, or should it be configurable?
2. **Join path search algorithm** — BFS shortest path or should we also support "all paths"?
3. **Skill file format** — Should we generate SKILL.md (Claude Code skills) or also support .cursorrules (older Cursor format)?
4. **Query pattern deduplication** — If 10 downstream models all `SELECT user_id, created_at FROM T`, should that collapse to one pattern with a count?
