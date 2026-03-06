# Table Brief Specification

## Purpose

Define the stable brief shape exposed by `tablebrief brief`.

## Requirements

### Requirement: Compact Table Brief
The system SHALL return a compact brief for each discovered model or table.

#### Scenario: JSON brief output
- WHEN a caller requests `tablebrief brief <table> --format json`
- THEN the output includes purpose, grain, keys, dependencies, exclusions, freshness, alternatives, confidence, and evidence

#### Scenario: Markdown brief output
- WHEN a caller requests `tablebrief brief <table> --format markdown`
- THEN the output renders the same brief information in human-readable Markdown

### Requirement: Evidence-Backed Inference
The system SHALL attach evidence references for inferred fields.

#### Scenario: field inferred from repo content
- WHEN purpose, grain, keys, exclusions, or freshness are inferred
- THEN the brief includes evidence entries pointing to files and line numbers

#### Scenario: weak signal
- WHEN the repository does not provide enough evidence for a field
- THEN the field stays empty instead of inventing business meaning

### Requirement: Alternative Suggestions
The system SHALL surface likely alternate tables when strong similarities exist.

#### Scenario: neighboring models
- WHEN two models have similar names or shared upstreams
- THEN the brief may include them in `alternatives`
