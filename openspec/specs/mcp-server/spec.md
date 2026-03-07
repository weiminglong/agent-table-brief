# MCP Server Specification

## Purpose

Define how `tablebrief serve` exposes the catalog over the Model Context Protocol so AI editors
and agents can query table briefs without shelling out to the CLI.

## Requirements

### Requirement: MCP Tools
The server SHALL expose catalog operations as MCP tools callable by any MCP client.

#### Scenario: search_tables tool
- WHEN an MCP client calls `search_tables` with a query string
- THEN the server returns ranked search results from the stored catalog

#### Scenario: get_brief tool
- WHEN an MCP client calls `get_brief` with a table name
- THEN the server returns the full brief for that table

#### Scenario: compare_tables tool
- WHEN an MCP client calls `compare_tables` with two or more table names
- THEN the server returns a structured comparison with differences highlighted

#### Scenario: list_tables tool
- WHEN an MCP client calls `list_tables`
- THEN the server returns all table names with purpose and confidence from the active scan

#### Scenario: list_repos tool
- WHEN an MCP client calls `list_repos`
- THEN the server returns all scanned repositories

### Requirement: MCP Resource
The server SHALL expose stored catalogs as MCP resources.

#### Scenario: catalog resource
- WHEN an MCP client reads `tablebrief://catalog/{repo_key}`
- THEN the server returns the full catalog JSON for that repository

### Requirement: Transport
The server SHALL use stdio transport by default.

#### Scenario: stdio server
- WHEN `tablebrief serve` is started
- THEN the server communicates via stdin/stdout using JSON-RPC

### Requirement: Optional Dependency
The MCP server SHALL only require the `mcp` package when actually running.

#### Scenario: missing mcp package
- WHEN a user runs `tablebrief serve` without the `mcp` extra installed
- THEN the command exits with an error message explaining how to install the dependency

#### Scenario: other commands unaffected
- WHEN a user runs `tablebrief scan`, `brief`, `search`, or other commands without the `mcp` extra
- THEN the commands work normally without importing the `mcp` package
