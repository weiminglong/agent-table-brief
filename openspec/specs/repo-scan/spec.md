# Repo Scan Specification

## Purpose

Define how `tablebrief scan` discovers analytics models and builds the local catalog store.

## Requirements

### Requirement: Repository Detection
The system SHALL detect whether the input path is a dbt project or a plain SQL repository.

#### Scenario: dbt project detected
- WHEN the scanned path contains `dbt_project.yml`
- THEN the scanner classifies the repository as `dbt`

#### Scenario: plain SQL repository detected
- WHEN the scanned path does not contain `dbt_project.yml` but includes SQL files
- THEN the scanner classifies the repository as `sql`

### Requirement: Local Catalog Generation
The system SHALL write scan results to a local SQLite-backed catalog store.

#### Scenario: default store path
- WHEN the caller does not override the catalog location
- THEN the catalog is written to `TABLEBRIEF_HOME/store.db` or the platform state directory fallback

#### Scenario: unchanged repository
- WHEN the same repository is scanned multiple times without file changes
- THEN the scanner reuses the active stored scan instead of duplicating brief rows

### Requirement: Repo-Native Metadata
The system SHALL derive context from repository files without requiring warehouse access.

#### Scenario: dbt metadata is present
- WHEN model SQL, YAML metadata, tests, or dbt manifest artifacts exist locally
- THEN the scanner uses them to enrich the catalog

#### Scenario: manifest missing
- WHEN a dbt repository has no local `target/manifest.json`
- THEN the scanner falls back to static file analysis
