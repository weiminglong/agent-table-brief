## MODIFIED Requirements

### Requirement: MCP Tools
The server SHALL expose catalog operations as MCP tools callable by any MCP client.

#### Scenario: search_tables tool
- **WHEN** an MCP client calls `search_tables` with a query string
- **THEN** the server returns ranked search results from the stored catalog

#### Scenario: get_brief tool
- **WHEN** an MCP client calls `get_brief` with a table name
- **THEN** the server returns the full brief for that table, including columns, joins, and query patterns

#### Scenario: compare_tables tool
- **WHEN** an MCP client calls `compare_tables` with two or more table names
- **THEN** the server returns a structured comparison with differences highlighted

#### Scenario: list_tables tool
- **WHEN** an MCP client calls `list_tables`
- **THEN** the server returns all table names with purpose and confidence from the active scan

#### Scenario: list_repos tool
- **WHEN** an MCP client calls `list_repos`
- **THEN** the server returns all scanned repositories

#### Scenario: get_columns tool
- **WHEN** an MCP client calls `get_columns` with a table name
- **THEN** the server returns the column list with names, types, descriptions, and sensitivity tags

#### Scenario: get_join_path tool
- **WHEN** an MCP client calls `get_join_path` with two table names
- **THEN** the server returns the shortest chain of joins connecting them, or empty if unconnected

#### Scenario: get_lineage tool
- **WHEN** an MCP client calls `get_lineage` with a table name and direction (upstream/downstream/both)
- **THEN** the server returns the multi-hop lineage graph with hop depths
