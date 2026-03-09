## Why

Agents and analysts need more than individual briefs — they need to understand how similar tables differ and which one is the right pick. The v0.1 `alternatives` field lists candidate tables but provides no detail on *why* they are similar or how they diverge. Adding a `compare` command, strengthening evidence mappings so every inferred field points at precise file ranges, and exposing per-field confidence scores closes the gap between "here are some tables" and "here is the right table."

## What Changes

- **New `compare` CLI command** that accepts two or more table names and returns a structured side-by-side diff highlighting shared and diverging purpose, grain, keys, filters, freshness, and dependencies.
- **Per-field confidence scores** added to the brief schema so callers know which parts of a brief are strong and which are speculative.
- **Stronger evidence mapping**: evidence refs for grain, keys, and filters now point at the specific SQL fragment or YAML block rather than the whole file.
- **Better alternatives scoring**: the similarity algorithm gains a grain-match bonus and a filter-divergence signal, producing more actionable alternative suggestions.

## Capabilities

### New Capabilities
- `table-compare`: Side-by-side structured comparison of two or more tables, exposed via `tablebrief compare`.

### Modified Capabilities
- `table-briefs`: Add `field_confidence` dict to the brief schema; tighten evidence references for grain, keys, and filters.
- `repo-scan`: Alternatives scoring gains grain-match bonus and filter-divergence signal.

## Impact

- **Models**: `TableBrief` gains a `field_confidence` field (dict mapping field names to float scores). `CompareResult` is a new Pydantic model.
- **CLI**: New `compare` command added to `cli.py`.
- **Render**: New `render_compare_json` / `render_compare_markdown` functions.
- **Repository**: `_infer_alternatives` updated with new scoring signals; evidence helpers produce narrower line ranges.
- **Storage**: `load_brief` already works for compare; no schema changes required.
- **Tests**: New tests for `compare` command, per-field confidence, and tighter evidence.
- **Backwards compatibility**: Additive changes only — no breaking changes to existing JSON output.
