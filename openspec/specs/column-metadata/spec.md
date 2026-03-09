## ADDED Requirements

### Requirement: Column Extraction
The system SHALL extract column-level metadata for each discovered table.

#### Scenario: columns from schema.yml
- **WHEN** a dbt model has columns defined in schema.yml with names and descriptions
- **THEN** the brief's `columns` list includes each column with its name, description, and evidence pointing at the YAML block

#### Scenario: columns from manifest.json
- **WHEN** a dbt manifest contains column metadata for a model
- **THEN** the scanner uses manifest columns to populate the brief, with manifest evidence

#### Scenario: columns from SQL SELECT
- **WHEN** a model's SQL contains a final SELECT with explicit column names (not SELECT *)
- **THEN** the scanner extracts column names from the SELECT list as a fallback

#### Scenario: columns from INFORMATION_SCHEMA
- **WHEN** a live DSN is provided and the table exists in the database
- **THEN** the scanner pulls column names, data types, and column comments from INFORMATION_SCHEMA.COLUMNS

#### Scenario: no columns found
- **WHEN** no column metadata is available from any source
- **THEN** the `columns` list is empty rather than speculative

### Requirement: Column Detail
Each column entry SHALL include name, inferred type, description, and tags when available.

#### Scenario: column with full metadata
- **WHEN** a column has name, type, and description from YAML or INFORMATION_SCHEMA
- **THEN** the column entry includes `name`, `type`, `description`, and a confidence score

#### Scenario: column with name only
- **WHEN** a column is extracted from SQL SELECT but has no type or description
- **THEN** the column entry includes `name` with null type and null description, and lower confidence

### Requirement: Column Sensitivity Tags
The system SHALL tag columns with sensitivity labels when evidence supports it.

#### Scenario: PII column detected
- **WHEN** a column name matches PII patterns (email, phone, ssn, address, ip_address) or has a dbt tag containing "pii"
- **THEN** the column entry includes a `pii` sensitivity tag

#### Scenario: no sensitivity evidence
- **WHEN** a column name does not match known sensitive patterns and has no sensitivity tags
- **THEN** no sensitivity tag is applied
