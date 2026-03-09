"""Agent discovery: generate skill files, rules, and AGENTS.md integration."""

from __future__ import annotations

from pathlib import Path

from agent_table_brief import __version__

VERSION_MARKER = f"<!-- tablebrief:{__version__} -->"

CLAUDE_SKILL = """\
{version_marker}
# TableBrief — Table Context Skill

**When to use**: Before writing SQL queries, ETL pipelines, dbt models,
database migrations, or any code that interacts with database tables.

**How to use**:

1. **Find the right table**: `tablebrief search "daily active users"`
2. **Understand a table**: `tablebrief brief mart.daily_active_users`
3. **Check columns & types**: `tablebrief brief mart.daily_active_users --format json`
   (look at the `columns` array for names, types, descriptions, PII tags)
4. **Find join paths**: check the `joins` array in the brief output
5. **Trace lineage**: `tablebrief lineage mart.daily_active_users --direction upstream`
6. **Compare similar tables**:
   `tablebrief compare mart.daily_active_users mart.daily_active_users_all`

**Before writing any SQL or database code**:
- Always run `tablebrief brief <table>` to understand purpose, grain, and columns
- Check `filters_or_exclusions` to avoid common mistakes (e.g., missing employee filter)
- Check `primary_keys` and `grain` to write correct GROUP BY clauses
- Check `joins` for pre-validated join conditions
- Check `alternatives` to ensure you're using the right table

**If tablebrief is not scanned yet**: Run `tablebrief scan .` first.
"""

CURSOR_RULES = """\
{version_marker}
# TableBrief — Table Context Rules

When working with SQL, dbt models, ETL pipelines, or database code:

1. Before writing queries, run `tablebrief brief <table>` to understand:
   - Purpose and grain (what each row represents)
   - Primary keys (for correct GROUP BY)
   - Filters/exclusions (e.g., "excludes employees")
   - Column metadata (names, types, PII tags)
   - Join paths (pre-validated join conditions)

2. To find tables: `tablebrief search "<description>"`
3. To trace dependencies: `tablebrief lineage <table> --direction upstream`
4. To compare similar tables: `tablebrief compare <table_a> <table_b>`

Always check `alternatives` before choosing a table — there may be a
better-suited variant (e.g., with/without employee data).

If the repository hasn't been scanned: `tablebrief scan .`
"""

AGENTS_MD_SECTION = """\
{version_marker}
## Table Context

This project uses [tablebrief](https://github.com/weiminglong/agent-table-brief) \
for database table understanding.

Before writing SQL, ETL, or database code:
- `tablebrief search "<query>"` — find tables by intent
- `tablebrief brief <table>` — get purpose, grain, columns, joins, lineage
- `tablebrief lineage <table>` — trace upstream/downstream dependencies
- `tablebrief compare <a> <b>` — diff similar tables

Run `tablebrief scan .` if the repository hasn't been scanned yet.
"""


def detect_agents(root: Path) -> list[str]:
    """Detect which AI agent directories exist in the project."""
    agents: list[str] = []
    if (root / ".claude").is_dir():
        agents.append("claude")
    if (root / ".cursor").is_dir():
        agents.append("cursor")
    if (root / ".windsurf").is_dir():
        agents.append("windsurf")
    return agents


def generate_init_files(
    root: Path,
    agents: list[str] | None = None,
) -> list[str]:
    """Generate agent discovery files. Returns list of created/updated paths."""
    created: list[str] = []

    if agents is None:
        agents = detect_agents(root)

    if "claude" in agents:
        path = _write_claude_skill(root)
        created.append(str(path.relative_to(root)))

    if "cursor" in agents:
        path = _write_cursor_rules(root)
        created.append(str(path.relative_to(root)))

    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        updated = _update_agents_md(agents_md)
        if updated:
            created.append("AGENTS.md")

    return created


def _write_claude_skill(root: Path) -> Path:
    skill_dir = root / ".claude" / "skills" / "tablebrief"
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    content = CLAUDE_SKILL.format(version_marker=VERSION_MARKER)
    path.write_text(content, encoding="utf-8")
    return path


def _write_cursor_rules(root: Path) -> Path:
    rules_dir = root / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / "tablebrief.md"
    content = CURSOR_RULES.format(version_marker=VERSION_MARKER)
    path.write_text(content, encoding="utf-8")
    return path


def _update_agents_md(agents_md: Path) -> bool:
    """Append Table Context section if not already present. Returns True if updated."""
    content = agents_md.read_text(encoding="utf-8")
    if "## Table Context" in content:
        # Check if version marker needs update
        if VERSION_MARKER in content:
            return False
        # Replace old section
        lines = content.split("\n")
        new_lines: list[str] = []
        skip = False
        for line in lines:
            if line.strip() == "## Table Context":
                skip = True
                continue
            if skip and line.startswith("## "):
                skip = False
            if not skip:
                new_lines.append(line)
        content = "\n".join(new_lines).rstrip() + "\n"
    section = AGENTS_MD_SECTION.format(version_marker=VERSION_MARKER)
    content = content.rstrip() + "\n\n" + section + "\n"
    agents_md.write_text(content, encoding="utf-8")
    return True
