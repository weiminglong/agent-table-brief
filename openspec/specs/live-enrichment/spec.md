## ADDED Requirements

### Requirement: Optional Database Connection
The system SHALL accept an optional database connection string to enrich scanned briefs with live schema metadata.

#### Scenario: DSN provided on scan
- **WHEN** a caller runs `tablebrief scan <path> --dsn <connection-string>`
- **THEN** the scanner connects to the database and pulls column types, descriptions, foreign key constraints, and table statistics

#### Scenario: DSN not provided
- **WHEN** no `--dsn` is supplied
- **THEN** the scanner operates in local-only mode with no behavior change from current functionality

#### Scenario: connection failure
- **WHEN** a DSN is provided but the database is unreachable
- **THEN** the scan completes using local-only analysis and emits a warning (not an error)

### Requirement: Live Schema Enrichment
The system SHALL merge live database metadata with locally-inferred metadata, preferring live data for type and constraint information.

#### Scenario: column type from database
- **WHEN** a column exists in both local schema.yml and the live database
- **THEN** the column type from the database takes precedence over any locally inferred type

#### Scenario: foreign key from database
- **WHEN** the database has foreign key constraints between tables
- **THEN** the scanner creates join path entries from those constraints with high confidence (0.95)

#### Scenario: row count from database
- **WHEN** the database provides table statistics
- **THEN** the brief includes a `row_count` hint in freshness_hints

### Requirement: Credential Safety
The system SHALL never persist connection strings or credentials in the catalog store.

#### Scenario: DSN not stored
- **WHEN** a scan completes with a DSN
- **THEN** the SQLite store contains enriched metadata but no trace of the connection string

#### Scenario: environment variable DSN
- **WHEN** `--dsn` value starts with `env:` (e.g., `env:DATABASE_URL`)
- **THEN** the scanner reads the connection string from the named environment variable
