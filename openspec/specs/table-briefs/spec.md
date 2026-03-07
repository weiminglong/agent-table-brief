# Table Brief Specification

## Purpose

Define the stable brief shape exposed by `tablebrief brief`.

## Requirements

### Requirement: Compact Table Brief
The system SHALL return a compact brief for each discovered model or table.

#### Scenario: JSON brief output
- WHEN a caller requests `tablebrief brief <table> --format json`
- THEN the output includes purpose, grain, keys, dependencies, exclusions, freshness, alternatives, confidence, field_confidence, and evidence

#### Scenario: Markdown brief output
- WHEN a caller requests `tablebrief brief <table> --format markdown`
- THEN the output renders the same brief information in human-readable Markdown, including per-field confidence scores

### Requirement: Per-Field Confidence Scores
The system SHALL expose per-field confidence scores so callers know which brief fields are strong and which are speculative.

#### Scenario: field_confidence in JSON output
- WHEN a brief is rendered as JSON
- THEN the output includes a `field_confidence` dict mapping field names (purpose, grain, primary_keys, derived_from, filters_or_exclusions, freshness_hints, downstream_usage, alternatives) to float scores between 0.0 and 1.0

#### Scenario: empty field gets zero confidence
- WHEN a brief field has no inferred value (e.g. grain is null)
- THEN the corresponding `field_confidence` entry is 0.0

### Requirement: Evidence-Backed Inference
The system SHALL attach evidence references for inferred fields.

#### Scenario: field inferred from repo content
- WHEN purpose, grain, keys, exclusions, or freshness are inferred
- THEN the brief includes evidence entries pointing to files and line numbers

#### Scenario: weak signal
- WHEN the repository does not provide enough evidence for a field
- THEN the field stays empty instead of inventing business meaning

### Requirement: Precise Evidence References
The system SHALL attach evidence references that point at specific file ranges rather than whole files when possible.

#### Scenario: grain evidence points at GROUP BY
- WHEN grain is inferred from a GROUP BY clause
- THEN the evidence ref start_line and end_line cover the GROUP BY fragment, not the entire SQL file

#### Scenario: key evidence points at test block
- WHEN primary keys are inferred from YAML tests
- THEN the evidence ref covers the relevant YAML test block

#### Scenario: filter evidence points at WHERE clause
- WHEN filters are inferred from WHERE clauses
- THEN the evidence ref covers the WHERE clause fragment

### Requirement: Alternative Suggestions
The system SHALL surface likely alternate tables when strong similarities exist.

#### Scenario: neighboring models
- WHEN two models have similar names or shared upstreams
- THEN the brief may include them in `alternatives`

#### Scenario: grain-match bonus
- WHEN two models share the same inferred grain
- THEN the alternatives scoring awards a grain-match bonus, increasing the likelihood they appear as alternatives

#### Scenario: filter-divergence signal
- WHEN two models share a name prefix but have different filter sets
- THEN the alternatives scoring awards a filter-divergence bonus, surfacing the pair as alternatives since they are the most confusing to distinguish
