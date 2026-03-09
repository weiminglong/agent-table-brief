## 1. Per-Field Confidence in Models and Repository

- [x] 1.1 Add `field_confidence: dict[str, float]` to `TableBrief` in `models.py` (default empty dict, included in JSON serialization)
- [x] 1.2 Update `_build_brief` in `repository.py` to populate `field_confidence` from the per-field scores already computed (purpose_score, grain_score, etc.)
- [x] 1.3 Add unit test verifying `field_confidence` is present and correct for a dbt fixture brief

## 2. Stronger Evidence Mapping

- [x] 2.1 Update `_infer_grain` to return evidence refs pointing at the GROUP BY fragment or composite key YAML block instead of the whole file
- [x] 2.2 Update `_infer_primary_keys` to return evidence refs pointing at the YAML test block or GROUP BY fragment instead of the whole file
- [x] 2.3 Refactor `_build_brief` to use grain and key evidence from the inference functions rather than `model.grain_evidence` / `model.key_evidence`
- [x] 2.4 Add unit test verifying grain and key evidence refs have narrower line ranges than the full file

## 3. Improved Alternatives Scoring

- [x] 3.1 Pass inferred grain and filters into `_infer_alternatives` and add grain-match bonus (+0.1) and filter-divergence signal (+0.15)
- [x] 3.2 Lower the alternatives threshold from 0.45 to 0.40
- [x] 3.3 Add unit test verifying that grain-match and filter-divergence boost alternatives ranking

## 4. Compare Command

- [x] 4.1 Add `CompareResult` and `CompareEntry` Pydantic models to `models.py`
- [x] 4.2 Add `build_compare_result` function to `repository.py` that loads briefs and computes differences dict
- [x] 4.3 Add `render_compare_json` and `render_compare_markdown` to `render.py`
- [x] 4.4 Add `compare` CLI command to `cli.py` accepting two or more table names with `--repo`, `--store`, and `--format` options
- [x] 4.5 Add CLI test for `compare` with two dbt fixture tables (JSON output)
- [x] 4.6 Add CLI test for `compare` with unknown table returning `brief_not_found` error

## 5. Render Updates

- [x] 5.1 Update `render_brief_markdown` to include per-field confidence scores
- [x] 5.2 Add test verifying markdown output includes field confidence section

## 6. Quality and Integration

- [x] 6.1 Run `ruff check .` and fix any lint issues
- [x] 6.2 Run `mypy src` and fix any type errors
- [x] 6.3 Run `pytest` and verify all tests pass
