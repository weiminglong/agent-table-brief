# Project Context

## Summary

`agent-table-brief` is a local-first CLI that scans analytics repositories and builds compact,
evidence-backed table briefs for coding agents and humans.

## Stack

- Python 3.12+
- `uv` for environment and dependency management
- `typer` for the CLI
- `pydantic` for public schemas
- `sqlglot` for SQL parsing
- `PyYAML` for YAML metadata
- `pytest`, `ruff`, `mypy` for quality gates

## Conventions

- The public CLI is `tablebrief`.
- The default catalog path is `.tablebrief/catalog.json`.
- Output should stay compact, deterministic, and agent-friendly.
- Evidence must always point back to concrete files and line ranges.
- Heuristics should prefer empty fields over speculative text.

## Planning Workflow

All future feature work starts in OpenSpec.

1. Create a change:
   `openspec new change <change-name>`
2. Capture intent in `proposal.md`, implementation decisions in `design.md`, and execution steps in
   `tasks.md`.
3. Add or update delta specs under `openspec/changes/<change-name>/specs/`.
4. Validate with `openspec validate <change-name>`.
5. Implement only after the change artifacts are aligned.
6. Archive with `openspec archive <change-name> --yes` once the work is complete.
