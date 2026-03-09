## ADDED Requirements

### Requirement: Init Command
The system SHALL provide a `tablebrief init` command that generates agent integration files for the current repository.

#### Scenario: init in a repo
- **WHEN** a caller runs `tablebrief init` in a project directory
- **THEN** the command generates skill files, editor rules, and agent instructions appropriate for the detected editors/agents

#### Scenario: init with scan
- **WHEN** a caller runs `tablebrief init --scan`
- **THEN** the command also performs an initial scan of the repository before generating integration files

#### Scenario: init idempotent
- **WHEN** `tablebrief init` is run in a directory that already has integration files
- **THEN** the command updates existing files to the latest version without duplicating content

### Requirement: Claude Code Skills
The system SHALL generate Claude Code skill files that teach agents to use tablebrief before writing database code.

#### Scenario: skill files generated
- **WHEN** `tablebrief init` runs and detects Claude Code usage (`.claude/` directory exists or `--agent claude` is specified)
- **THEN** skill files are written to `.claude/skills/tablebrief/` with instructions for table discovery, brief lookup, and column inspection

#### Scenario: skill auto-triggers on SQL
- **WHEN** a Claude Code agent encounters a task involving SQL, ETL, or database code
- **THEN** the generated skill instructions direct the agent to search tablebrief for relevant tables before writing queries

### Requirement: Cursor Rules
The system SHALL generate Cursor rules that make tablebrief MCP tools available.

#### Scenario: cursor rules generated
- **WHEN** `tablebrief init` runs and detects Cursor usage (`.cursor/` directory exists or `--agent cursor` is specified)
- **THEN** a rules file is written to `.cursor/rules/tablebrief.md` with instructions for using tablebrief MCP tools

### Requirement: MCP Configuration
The system SHALL generate MCP server configuration for supported editors.

#### Scenario: Claude Desktop config
- **WHEN** `tablebrief init --agent claude-desktop` is run
- **THEN** the command outputs the JSON snippet to add to `claude_desktop_config.json`

#### Scenario: Cursor MCP config
- **WHEN** `tablebrief init` detects Cursor
- **THEN** a `.cursor/mcp.json` entry is generated for the tablebrief MCP server

### Requirement: AGENTS.md Integration
The system SHALL append tablebrief usage instructions to the repository's AGENTS.md if present.

#### Scenario: AGENTS.md exists
- **WHEN** `tablebrief init` runs and AGENTS.md exists in the repo root
- **THEN** the command appends a "Table Context" section with instructions for using tablebrief CLI and MCP tools

#### Scenario: no AGENTS.md
- **WHEN** AGENTS.md does not exist
- **THEN** the command skips AGENTS.md integration silently
