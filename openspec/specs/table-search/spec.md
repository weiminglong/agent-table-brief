# Table Search Specification

## Purpose

Define how `tablebrief search` finds tables by keyword across the stored catalog.

## Requirements

### Requirement: Full-Text Search
The system SHALL search over brief fields using SQLite FTS5 and return ranked results.

#### Scenario: JSON search output
- WHEN a caller runs `tablebrief search "<query>" --format json`
- THEN the output includes the query string and a list of hits ranked by BM25 relevance, each containing the table name, rank score, and full brief

#### Scenario: Markdown search output
- WHEN a caller runs `tablebrief search "<query>" --format markdown`
- THEN the output renders a human-readable ranked list with purpose, grain, confidence, and rank for each hit

#### Scenario: no matching tables
- WHEN the query does not match any indexed brief fields
- THEN the output contains an empty hits list

### Requirement: Result Limiting
The system SHALL support limiting the number of returned results.

#### Scenario: limit option
- WHEN `--limit N` is supplied
- THEN at most N hits are returned, ordered by relevance

### Requirement: Repo Scoping
The system SHALL scope search results to a single repository when `--repo` is provided.

#### Scenario: repo filter
- WHEN `--repo <path>` is supplied
- THEN only briefs from the active scan of that repository are searched

#### Scenario: unscanned repo
- WHEN the specified repo has not been scanned
- THEN the command exits non-zero with a `repo_not_scanned` error
