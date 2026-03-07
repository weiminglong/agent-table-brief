## MODIFIED Requirements

### Requirement: Compact Table Brief
The system SHALL return a compact brief for each discovered model or table.

#### Scenario: JSON brief output
- **WHEN** a caller requests `tablebrief brief <table> --format json`
- **THEN** the output includes purpose, grain, keys, dependencies, exclusions, freshness, alternatives, confidence, evidence, and field_confidence

#### Scenario: Markdown brief output
- **WHEN** a caller requests `tablebrief brief <table> --format markdown`
- **THEN** the output renders the same brief information in human-readable Markdown, including per-field confidence scores

## ADDED Requirements

### Requirement: Per-Field Confidence Scores
The system SHALL expose per-field confidence scores so callers know which brief fields are strong and which are speculative.

#### Scenario: field_confidence in JSON output
- **WHEN** a brief is rendered as JSON
- **THEN** the output includes a `field_confidence` dict mapping field names (purpose, grain, primary_keys, derived_from, filters_or_exclusions, freshness_hints, downstream_usage, alternatives) to float scores between 0.0 and 1.0

#### Scenario: empty field gets zero confidence
- **WHEN** a brief field has no inferred value (e.g. grain is null)
- **THEN** the corresponding `field_confidence` entry is 0.0

### Requirement: Precise Evidence References
The system SHALL attach evidence references that point at specific file ranges rather than whole files when possible.

#### Scenario: grain evidence points at GROUP BY
- **WHEN** grain is inferred from a GROUP BY clause
- **THEN** the evidence ref start_line and end_line cover the GROUP BY fragment, not the entire SQL file

#### Scenario: key evidence points at test block
- **WHEN** primary keys are inferred from YAML tests
- **THEN** the evidence ref covers the relevant YAML test block

#### Scenario: filter evidence points at WHERE clause
- **WHEN** filters are inferred from WHERE clauses
- **THEN** the evidence ref covers the WHERE clause fragment
