# Catalog Export Specification

## Purpose

Define how `tablebrief export` emits the saved catalog for agents and humans.

## Requirements

### Requirement: Export Stored Catalog
The system SHALL export the existing stored catalog without rescanning the repository.

#### Scenario: JSON export
- WHEN the caller runs `tablebrief export --format json`
- THEN the command emits the full saved catalog as JSON

#### Scenario: Markdown export
- WHEN the caller runs `tablebrief export --format markdown`
- THEN the command emits the full saved catalog as Markdown

### Requirement: Explicit Output Destination
The system SHALL support writing exports to a file path.

#### Scenario: output file provided
- WHEN `--output <path>` is supplied
- THEN the command writes the rendered export to that file and keeps the catalog unchanged
