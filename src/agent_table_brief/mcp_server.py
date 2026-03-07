from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agent_table_brief.repository import build_compare_result
from agent_table_brief.storage import CatalogStore, resolve_store_path

mcp = FastMCP(
    "tablebrief",
    instructions=(
        "tablebrief provides table-level context for analytics repositories. "
        "Use search_tables to find tables by intent, get_brief for full detail "
        "on a specific table, compare_tables to diff similar tables, "
        "list_tables for a catalog overview, and list_repos to see scanned repositories. "
        "All data comes from a local scan — no warehouse connection required."
    ),
)


def _store() -> CatalogStore:
    env_store = os.environ.get("TABLEBRIEF_STORE")
    override = Path(env_store) if env_store else None
    return CatalogStore(resolve_store_path(override))


@mcp.tool()
def search_tables(query: str, repo: str | None = None, limit: int = 10) -> str:
    """Search for tables by keyword across purpose, grain, filters, and table names.

    Use this as the starting point when you need to find the right table for a query.
    Results are ranked by BM25 relevance. Each hit includes the full brief with
    purpose, grain, keys, dependencies, filters, freshness, alternatives, confidence,
    and evidence.

    Args:
        query: Natural language search terms (e.g. "daily active users").
        repo: Path to the scanned repository. Omit to use the current directory.
        limit: Maximum number of results to return.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    result = store.search(query, repo_path=repo_path, limit=limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
def get_brief(table: str, repo: str | None = None) -> str:
    """Get the full brief for a specific table.

    Returns purpose, grain, primary_keys, derived_from, filters_or_exclusions,
    freshness_hints, downstream_usage, alternatives, confidence, field_confidence,
    and evidence. Use the fully qualified name (e.g. "mart.daily_active_users")
    or the short name if unambiguous.

    Args:
        table: Table name, e.g. "mart.daily_active_users" or "daily_active_users".
        repo: Path to the scanned repository. Omit to use the current directory.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    brief = store.load_brief(table, repo_path=repo_path)
    return brief.model_dump_json(indent=2)


@mcp.tool()
def compare_tables(tables: list[str], repo: str | None = None) -> str:
    """Compare two or more tables side-by-side.

    Returns each table's full brief plus a differences dict that maps diverging
    field names (purpose, grain, primary_keys, filters_or_exclusions, etc.) to
    the distinct values across the compared tables. Use this when you need to
    decide between similar tables.

    Args:
        tables: Two or more table names to compare.
        repo: Path to the scanned repository. Omit to use the current directory.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    briefs = [store.load_brief(t, repo_path=repo_path) for t in tables]
    result = build_compare_result(briefs)
    return result.model_dump_json(indent=2)


@mcp.tool()
def list_tables(repo: str | None = None) -> str:
    """List all tables in the stored catalog for a repository.

    Returns an array of objects with table (name), purpose (string), and
    confidence (float 0-1). Use this to get a quick overview before calling
    get_brief on specific tables.

    Args:
        repo: Path to the scanned repository. Omit to use the current directory.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    catalog = store.load_catalog(repo_path=repo_path)
    entries = [
        {"table": b.table, "purpose": b.purpose, "confidence": b.confidence}
        for b in catalog.briefs
    ]
    import json

    return json.dumps(entries, indent=2)


@mcp.tool()
def list_repos() -> str:
    """List all scanned repositories in the catalog store.

    Returns an array of objects with repo_key, repo_root, effective_root,
    project_type, brief_count, and generated_at. Call this first if you are
    unsure which repository to query.
    """
    store = _store()
    summaries = store.list_repos()
    import json

    return json.dumps(
        [s.model_dump(mode="json") for s in summaries],
        indent=2,
    )


@mcp.resource("tablebrief://catalog/{repo_key}")
def get_catalog(repo_key: str) -> str:
    """Return the full catalog JSON for a repository by its repo key."""
    store = _store()
    summaries = store.list_repos()
    match = next((s for s in summaries if s.repo_key == repo_key), None)
    if match is None:
        return f'{{"error": "Repository not found: {repo_key}"}}'
    catalog = store.load_catalog(repo_path=Path(match.effective_root))
    return catalog.model_dump_json(indent=2)


def run_server() -> None:
    mcp.run()
