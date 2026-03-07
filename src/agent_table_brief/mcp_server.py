from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agent_table_brief.repository import build_compare_result
from agent_table_brief.storage import CatalogStore, resolve_store_path

mcp = FastMCP("tablebrief")


def _store() -> CatalogStore:
    env_store = os.environ.get("TABLEBRIEF_STORE")
    override = Path(env_store) if env_store else None
    return CatalogStore(resolve_store_path(override))


@mcp.tool()
def search_tables(query: str, repo: str | None = None, limit: int = 10) -> str:
    """Search for tables by keyword across purpose, grain, filters, and names.

    Returns ranked results from the stored catalog.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    result = store.search(query, repo_path=repo_path, limit=limit)
    return result.model_dump_json(indent=2)


@mcp.tool()
def get_brief(table: str, repo: str | None = None) -> str:
    """Get the full brief for a specific table.

    Returns purpose, grain, keys, dependencies, exclusions, freshness,
    alternatives, confidence, and evidence.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    brief = store.load_brief(table, repo_path=repo_path)
    return brief.model_dump_json(indent=2)


@mcp.tool()
def compare_tables(tables: list[str], repo: str | None = None) -> str:
    """Compare two or more tables side-by-side.

    Returns a structured diff highlighting shared and diverging fields.
    """
    store = _store()
    repo_path = Path(repo) if repo else None
    briefs = [store.load_brief(t, repo_path=repo_path) for t in tables]
    result = build_compare_result(briefs)
    return result.model_dump_json(indent=2)


@mcp.tool()
def list_tables(repo: str | None = None) -> str:
    """List all tables in the stored catalog for a repository.

    Returns table names with purpose and confidence.
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
    """List all scanned repositories in the catalog store."""
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
