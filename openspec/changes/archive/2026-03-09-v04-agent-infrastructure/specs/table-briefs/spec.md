## MODIFIED Requirements

### Requirement: Compact Table Brief
The system SHALL return a compact brief for each discovered model or table.

#### Scenario: JSON brief output
- **WHEN** a caller requests `tablebrief brief <table> --format json`
- **THEN** the output includes purpose, grain, keys, dependencies, exclusions, freshness, alternatives, confidence, field_confidence, evidence, columns, joins, and query_patterns

#### Scenario: Markdown brief output
- **WHEN** a caller requests `tablebrief brief <table> --format markdown`
- **THEN** the output renders the same brief information in human-readable Markdown, including per-field confidence scores, column details, join paths, and query patterns

### Requirement: Per-Field Confidence Scores
The system SHALL expose per-field confidence scores so callers know which brief fields are strong and which are speculative.

#### Scenario: field_confidence in JSON output
- **WHEN** a brief is rendered as JSON
- **THEN** the output includes a `field_confidence` dict mapping field names (purpose, grain, primary_keys, derived_from, filters_or_exclusions, freshness_hints, downstream_usage, alternatives, columns, joins) to float scores between 0.0 and 1.0

#### Scenario: empty field gets zero confidence
- **WHEN** a brief field has no inferred value (e.g. grain is null)
- **THEN** the corresponding `field_confidence` entry is 0.0
