## MODIFIED Requirements

### Requirement: Full-Text Search Index
The system SHALL populate an FTS5 full-text index at scan time so briefs are searchable.

#### Scenario: FTS index populated
- **WHEN** a scan completes successfully
- **THEN** the FTS index contains entries for each brief's table name, purpose, grain, filters, alternatives, and column names

## ADDED Requirements

### Requirement: Column Extraction During Scan
The system SHALL extract column-level metadata during the scan phase from schema.yml, manifest.json, SQL SELECT lists, and optionally INFORMATION_SCHEMA.

#### Scenario: columns extracted from dbt project
- **WHEN** a dbt project is scanned with schema.yml column definitions
- **THEN** each brief includes a `columns` list with name, description, and evidence

#### Scenario: columns extracted from SQL
- **WHEN** a plain SQL model has an explicit SELECT list (not SELECT *)
- **THEN** column names are extracted from the final SELECT

### Requirement: Join Inference During Scan
The system SHALL infer join relationships between tables during the scan phase.

#### Scenario: joins inferred from dbt refs
- **WHEN** model SQL uses `{{ ref('other_model') }}` with a JOIN or WHERE equi-join
- **THEN** the scanner records a join path between the two models

#### Scenario: joins inferred from relationship tests
- **WHEN** schema.yml defines a `relationships` test
- **THEN** the scanner records a join path from the test definition

### Requirement: Optional Live Database Enrichment
The system SHALL accept an optional `--dsn` argument to enrich scanned results with live database metadata.

#### Scenario: scan with DSN
- **WHEN** `tablebrief scan <path> --dsn <connection-string>` is run
- **THEN** the scanner supplements local analysis with column types, FK constraints, and table statistics from the database

#### Scenario: scan without DSN
- **WHEN** no `--dsn` is provided
- **THEN** the scan operates identically to current behavior
