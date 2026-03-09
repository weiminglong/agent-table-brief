## ADDED Requirements

### Requirement: Join Path Inference
The system SHALL infer join paths between tables from ref()/source() calls, WHERE equi-joins, and YAML relationship tests.

#### Scenario: join inferred from ref()
- **WHEN** model A references model B via `{{ ref('B') }}` and the SQL contains a JOIN or WHERE clause equating columns from both
- **THEN** the brief for A includes a join path entry with the source table, target table, source column, and target column

#### Scenario: join inferred from WHERE equi-join
- **WHEN** a SQL WHERE clause contains `a.column_x = b.column_y` and both tables are identified
- **THEN** the scanner records a join path between the two tables on those columns

#### Scenario: join inferred from YAML tests
- **WHEN** a dbt schema.yml defines a `relationships` test linking a column to another table's column
- **THEN** the scanner records a join path from the test definition with high confidence

#### Scenario: no join evidence
- **WHEN** no equi-join, ref(), or relationship test connects two tables
- **THEN** no join path is inferred between them

### Requirement: Join Path Detail
Each join path entry SHALL include source table, target table, column pairs, join type when detectable, and confidence.

#### Scenario: join path JSON shape
- **WHEN** a brief with join paths is rendered as JSON
- **THEN** each entry in the `joins` list contains `to_table`, `on` (list of column pairs), `type` (inner/left/right/full or null), and `confidence`

### Requirement: Cross-Catalog Join Graph
The system SHALL expose a queryable join graph across all tables in a scanned repository.

#### Scenario: get_join_path query
- **WHEN** a caller asks for the join path between two tables that are connected through one or more intermediate tables
- **THEN** the system returns the shortest chain of join paths connecting them

#### Scenario: unconnected tables
- **WHEN** two tables have no direct or transitive join path
- **THEN** the system returns an empty path
