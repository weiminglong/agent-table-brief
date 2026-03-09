## ADDED Requirements

### Requirement: Query Pattern Extraction
The system SHALL extract example query patterns from downstream models to show how a table is typically used.

#### Scenario: downstream model references table
- **WHEN** model B selects from model A and the SQL is parseable
- **THEN** the scanner extracts the relevant SELECT columns, JOIN conditions, and WHERE filters as a query pattern for table A

#### Scenario: multiple downstream consumers
- **WHEN** a table is referenced by three or more downstream models
- **THEN** the brief includes up to 5 query patterns, ordered by relevance (most columns selected first)

#### Scenario: no downstream models
- **WHEN** a table has no known downstream consumers
- **THEN** the `query_patterns` list is empty

### Requirement: Query Pattern Detail
Each query pattern SHALL include the consuming model, columns used, joins applied, and filters applied.

#### Scenario: query pattern JSON shape
- **WHEN** a brief with query patterns is rendered as JSON
- **THEN** each entry in `query_patterns` contains `source_model` (the downstream model name), `columns_used` (list of column names selected), `joins` (list of join descriptions), and `filters` (list of WHERE conditions)

### Requirement: Common Column Usage
The system SHALL aggregate column usage across all downstream query patterns to surface which columns are most commonly selected.

#### Scenario: column usage summary
- **WHEN** a table's columns are referenced across multiple downstream models
- **THEN** the brief includes a `column_usage` dict mapping column names to usage counts across downstream models
