# Contributing

Thanks for contributing to `agent-table-brief`.

## Setup

```bash
uv sync --all-groups
```

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
uv run ruff check .
uv run mypy src
uv run pytest
openspec validate --specs
```

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
