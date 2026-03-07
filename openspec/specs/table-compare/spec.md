# Table Compare Specification

## Purpose

Define how `tablebrief compare` produces structured side-by-side comparisons of two or more
tables.

## Requirements

### Requirement: Compare Tables Side-by-Side
The system SHALL accept two or more table names and return a structured comparison highlighting
shared and diverging fields.

#### Scenario: JSON compare output
- WHEN a caller runs `tablebrief compare <tableA> <tableB> --format json`
- THEN the output includes each table's brief and a `differences` dict mapping diverging field names to lists of distinct values

#### Scenario: Markdown compare output
- WHEN a caller runs `tablebrief compare <tableA> <tableB> --format markdown`
- THEN the output renders a human-readable side-by-side comparison

#### Scenario: More than two tables
- WHEN a caller provides three or more table names
- THEN the comparison includes all provided tables

#### Scenario: Unknown table in compare
- WHEN one of the provided table names does not exist in the catalog
- THEN the command exits non-zero with a `brief_not_found` error

### Requirement: Compare Uses Stored Catalog
The system SHALL load briefs from the existing stored catalog without rescanning the repository.

#### Scenario: Compare after scan
- WHEN the repository has been scanned and two table names are provided
- THEN the compare command loads briefs from the active stored scan
