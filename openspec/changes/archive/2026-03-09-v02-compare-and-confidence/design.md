## Context

Tablebrief v0.1 provides scan, brief, and export commands. Each brief already contains `alternatives`, `confidence`, and `evidence` fields. However:

- `confidence` is a single float with no per-field breakdown, so callers cannot tell whether the purpose is strong but the grain is guessed.
- `evidence` refs for grain, keys, and filters often span the entire file rather than the relevant SQL fragment.
- `alternatives` scoring uses name similarity and Jaccard dependency overlap but misses semantic signals like matching grain or diverging filters.
- There is no way to compare two tables side-by-side.

The codebase is a single Python package (`agent_table_brief`) with modules: `cli.py`, `models.py`, `repository.py`, `render.py`, `storage.py`. All are under 650 lines.

## Goals / Non-Goals

**Goals:**
- Add a `compare` CLI command that loads two or more briefs and emits a structured diff.
- Expose per-field confidence scores (`field_confidence`) in the `TableBrief` schema.
- Narrow evidence references for grain, keys, and filter fields to specific line ranges.
- Improve alternatives scoring with grain-match bonus and filter-divergence signal.

**Non-Goals:**
- Changing the SQLite schema or adding new database tables.
- Semantic / LLM-based analysis of table meaning.
- Breaking changes to the existing JSON brief output shape.

## Decisions

### 1. `field_confidence` representation

**Choice:** Add a `field_confidence: dict[str, float]` field to `TableBrief`, defaulting to an empty dict, serialized in JSON output.

**Rationale:** A flat dict keyed by field name (`purpose`, `grain`, `primary_keys`, etc.) is the simplest structure that lets callers inspect per-field scores. Using the same field names as the brief itself makes the mapping self-documenting. Defaulting to empty dict keeps backward compatibility — old stored payloads will deserialize fine.

**Alternative considered:** Wrapping each field in a `{value, confidence}` object. Rejected because it breaks the brief shape and makes the JSON harder for agents to consume.

### 2. Compare output model

**Choice:** A new `CompareResult` Pydantic model containing a list of `CompareEntry` items, one per table, plus a `differences` dict that highlights diverging fields.

**Rationale:** Returning the full brief per table alongside a structured diff gives callers both the raw data and the actionable summary. The `differences` dict maps field names to a list of distinct values across the compared tables, making it trivial to spot the field that distinguishes two similar tables.

### 3. Evidence tightening approach

**Choice:** Modify `_infer_grain`, `_infer_primary_keys`, and `_derive_filters` to return `EvidenceRef` lists that point at the specific SQL fragment (GROUP BY clause, WHERE clause, YAML test block) instead of the whole file. Reuse the existing `_make_fragment_evidence` helper.

**Rationale:** The infrastructure for fragment-level evidence already exists — `_derive_filters` and `_derive_description` already produce narrow refs. Grain and key inference currently call `_make_file_evidence` (whole file). Switching to `_make_fragment_evidence` with the relevant SQL text is a small change.

### 4. Improved alternatives scoring

**Choice:** Add two new scoring signals to `_infer_alternatives`:
- **grain-match bonus (+0.1):** awarded when two models share the same inferred grain.
- **filter-divergence signal (+0.15):** awarded when two models share a name prefix but have different filter sets, since these are the most confusing pairs.

Adjust the score threshold from 0.45 to 0.40 to account for the richer signal space.

**Rationale:** The most common analyst mistake is picking the wrong table when two models are named alike but differ only in exclusion filters. Boosting these pairs surfaces the right alternatives.

## Risks / Trade-offs

- **Confidence recalibration**: Per-field scores may shift the aggregate confidence value slightly for existing briefs. Mitigation: unit tests validate that existing fixture briefs remain within ±0.05 of their current values.
- **Evidence precision**: Fragment evidence depends on `_make_fragment_evidence` finding the text snippet in the source. If the SQL is heavily Jinja-templated, the fragment may not match. Mitigation: fall back to whole-file evidence when fragment search returns line 1.
- **Compare memory**: Loading N briefs into memory is fine for typical catalogs (< 10k tables). No mitigation needed.
