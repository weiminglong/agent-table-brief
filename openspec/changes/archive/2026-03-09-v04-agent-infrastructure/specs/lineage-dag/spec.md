## ADDED Requirements

### Requirement: Multi-Hop Lineage
The system SHALL expose full upstream and downstream lineage beyond direct dependencies.

#### Scenario: upstream lineage
- **WHEN** a caller requests upstream lineage for a table
- **THEN** the system returns all transitive upstream tables with hop depth, not just direct `derived_from`

#### Scenario: downstream lineage
- **WHEN** a caller requests downstream lineage for a table
- **THEN** the system returns all transitive downstream tables with hop depth, not just direct `downstream_usage`

#### Scenario: lineage depth limit
- **WHEN** a caller specifies `--depth N`
- **THEN** the lineage traversal stops at N hops from the origin table

### Requirement: Lineage CLI Command
The system SHALL expose lineage traversal via a `tablebrief lineage` CLI command.

#### Scenario: JSON lineage output
- **WHEN** a caller runs `tablebrief lineage <table> --direction upstream --format json`
- **THEN** the output includes the origin table and a list of nodes with table name, hop depth, and relationship type

#### Scenario: Markdown lineage output
- **WHEN** a caller runs `tablebrief lineage <table> --direction downstream --format markdown`
- **THEN** the output renders a human-readable tree showing the lineage chain

#### Scenario: both directions
- **WHEN** a caller runs `tablebrief lineage <table> --direction both`
- **THEN** the output includes both upstream and downstream lineage from the origin
