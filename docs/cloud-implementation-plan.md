# tablebrief-cloud Implementation Plan

This document is the complete implementation plan for `tablebrief-cloud`, the SaaS
layer that adds team sharing to the open-source `agent-table-brief` CLI. It is
written for a coding agent and contains all the context needed to build the cloud
product from scratch.

## Architecture Overview

```
tablebrief-cloud (this repo, private)
    │
    │  depends on
    ▼
agent-table-brief (public, MIT)
    │
    │  provides
    ▼
Catalog, TableBrief, SearchResult, CompareResult, ScanResult
scan_repository(), build_compare_result()
```

The open-source CLI handles all inference logic (scanning repos, building briefs).
The cloud layer handles team auth, storage, sharing, the web dashboard, and the
hosted MCP endpoint. The cloud layer never reimplements inference — it imports
models and uses the Catalog JSON produced by the CLI.

### Why not a submodule

`agent-table-brief` is a Python package. Install it as a dependency:

```
uv add "agent-table-brief @ git+https://github.com/weiminglong/agent-table-brief.git"
```

This gives the cloud layer direct access to all Pydantic models (`TableBrief`,
`Catalog`, `SearchResult`, etc.) and utility functions. A submodule would duplicate
the source, create merge conflicts, and conflate release cycles.

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 15 (App Router) | Web dashboard |
| Hosting | Vercel | Frontend + API routes + Edge Functions |
| Database | Supabase (Postgres 15+) | Catalog storage, FTS, RLS |
| Auth | Supabase Auth | Email, Google OAuth, team management |
| MCP proxy | Vercel Edge Function | Hosted MCP endpoint for agents |
| Styling | Tailwind CSS + shadcn/ui | Component library |
| Language | TypeScript (frontend), Python (API) | |
| Monorepo | Turborepo | Manage apps + packages |

## Project Structure

```
tablebrief-cloud/
├── apps/
│   └── web/                          # Next.js app (Vercel)
│       ├── app/
│       │   ├── (auth)/
│       │   │   ├── login/page.tsx
│       │   │   └── signup/page.tsx
│       │   ├── (dashboard)/
│       │   │   ├── layout.tsx        # Sidebar, team switcher
│       │   │   ├── page.tsx          # Dashboard home
│       │   │   ├── catalogs/
│       │   │   │   ├── page.tsx      # List catalogs
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx  # Catalog detail (table list)
│       │   │   ├── briefs/
│       │   │   │   └── [table]/
│       │   │   │       └── page.tsx  # Brief detail view
│       │   │   ├── search/
│       │   │   │   └── page.tsx      # Full-text search
│       │   │   ├── compare/
│       │   │   │   └── page.tsx      # Side-by-side compare
│       │   │   └── settings/
│       │   │       ├── page.tsx      # Team settings
│       │   │       ├── members/
│       │   │       │   └── page.tsx  # Team members
│       │   │       └── api-keys/
│       │   │           └── page.tsx  # API key management
│       │   └── api/
│       │       ├── v1/
│       │       │   ├── upload/route.ts
│       │       │   ├── catalogs/route.ts
│       │       │   ├── briefs/[table]/route.ts
│       │       │   ├── search/route.ts
│       │       │   ├── compare/route.ts
│       │       │   └── repos/route.ts
│       │       └── mcp/
│       │           └── route.ts      # Hosted MCP endpoint (SSE)
│       ├── components/
│       │   ├── brief-card.tsx
│       │   ├── brief-detail.tsx
│       │   ├── catalog-table.tsx
│       │   ├── compare-view.tsx
│       │   ├── search-results.tsx
│       │   ├── confidence-badge.tsx
│       │   ├── evidence-list.tsx
│       │   ├── team-switcher.tsx
│       │   └── api-key-form.tsx
│       ├── lib/
│       │   ├── supabase/
│       │   │   ├── client.ts         # Browser client
│       │   │   ├── server.ts         # Server client
│       │   │   └── middleware.ts     # Auth middleware
│       │   ├── api-auth.ts           # API key validation
│       │   └── types.ts              # Shared TypeScript types
│       └── package.json
├── supabase/
│   ├── config.toml
│   └── migrations/
│       ├── 001_teams.sql
│       ├── 002_catalogs.sql
│       ├── 003_briefs.sql
│       ├── 004_api_keys.sql
│       ├── 005_audit_log.sql
│       └── 006_rls_policies.sql
├── packages/
│   └── shared/                       # Shared types/utils
│       ├── src/
│       │   └── types.ts
│       └── package.json
├── turbo.json
├── package.json
├── AGENTS.md
└── README.md
```

## Supabase Schema

### Migration 001: Teams

```sql
create table teams (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  slug        text not null unique,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table team_members (
  team_id     uuid not null references teams(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  role        text not null default 'member' check (role in ('owner', 'admin', 'member')),
  joined_at   timestamptz not null default now(),
  primary key (team_id, user_id)
);

create index idx_team_members_user on team_members(user_id);
```

### Migration 002: Catalogs

```sql
create table catalogs (
  id              uuid primary key default gen_random_uuid(),
  team_id         uuid not null references teams(id) on delete cascade,
  repo_key        text not null,
  repo_root       text not null,
  effective_root  text not null,
  project_type    text not null,
  scanner_version text not null,
  brief_count     integer not null,
  uploaded_by     uuid not null references auth.users(id),
  created_at      timestamptz not null default now(),
  unique (team_id, repo_key)
);

create index idx_catalogs_team on catalogs(team_id);
```

### Migration 003: Briefs

```sql
create table briefs (
  id              uuid primary key default gen_random_uuid(),
  catalog_id      uuid not null references catalogs(id) on delete cascade,
  team_id         uuid not null references teams(id) on delete cascade,
  table_name      text not null,
  short_name      text not null,
  purpose         text,
  grain           text,
  confidence      real not null,
  payload_json    jsonb not null,
  unique (catalog_id, table_name)
);

create index idx_briefs_catalog on briefs(catalog_id);
create index idx_briefs_team on briefs(team_id);
create index idx_briefs_short_name on briefs(team_id, short_name);

-- Full-text search index across brief fields
alter table briefs add column fts tsvector
  generated always as (
    setweight(to_tsvector('english', coalesce(table_name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(purpose, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(grain, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(
      payload_json->>'filters_or_exclusions', ''
    )), 'D')
  ) stored;

create index idx_briefs_fts on briefs using gin(fts);
```

### Migration 004: API Keys

```sql
create table api_keys (
  id          uuid primary key default gen_random_uuid(),
  team_id     uuid not null references teams(id) on delete cascade,
  name        text not null,
  key_hash    text not null unique,
  key_prefix  text not null,
  scope       text not null default 'read' check (scope in ('read', 'write', 'admin')),
  created_by  uuid not null references auth.users(id),
  last_used   timestamptz,
  created_at  timestamptz not null default now()
);

create index idx_api_keys_team on api_keys(team_id);
create index idx_api_keys_hash on api_keys(key_hash);
```

### Migration 005: Audit Log

```sql
create table audit_log (
  id          bigint generated always as identity primary key,
  team_id     uuid not null references teams(id) on delete cascade,
  user_id     uuid references auth.users(id),
  action      text not null,
  resource    text not null,
  detail      jsonb default '{}',
  ip_address  inet,
  created_at  timestamptz not null default now()
);

create index idx_audit_team_created on audit_log(team_id, created_at desc);
```

### Migration 006: RLS Policies

```sql
alter table teams enable row level security;
alter table team_members enable row level security;
alter table catalogs enable row level security;
alter table briefs enable row level security;
alter table api_keys enable row level security;
alter table audit_log enable row level security;

-- Teams: members can read their teams
create policy team_read on teams for select using (
  id in (select team_id from team_members where user_id = auth.uid())
);

-- Team members: members can read their team's membership
create policy team_members_read on team_members for select using (
  team_id in (select team_id from team_members where user_id = auth.uid())
);

-- Catalogs: team members can read, writers can insert
create policy catalogs_read on catalogs for select using (
  team_id in (select team_id from team_members where user_id = auth.uid())
);
create policy catalogs_insert on catalogs for insert with check (
  team_id in (
    select team_id from team_members
    where user_id = auth.uid() and role in ('owner', 'admin', 'member')
  )
);

-- Briefs: team members can read
create policy briefs_read on briefs for select using (
  team_id in (select team_id from team_members where user_id = auth.uid())
);
create policy briefs_insert on briefs for insert with check (
  team_id in (select team_id from team_members where user_id = auth.uid())
);

-- API keys: admins and owners can manage
create policy api_keys_read on api_keys for select using (
  team_id in (
    select team_id from team_members
    where user_id = auth.uid() and role in ('owner', 'admin')
  )
);
create policy api_keys_insert on api_keys for insert with check (
  team_id in (
    select team_id from team_members
    where user_id = auth.uid() and role in ('owner', 'admin')
  )
);

-- Audit log: admins can read
create policy audit_read on audit_log for select using (
  team_id in (
    select team_id from team_members
    where user_id = auth.uid() and role in ('owner', 'admin')
  )
);
```

## API Routes

All API routes are Next.js Route Handlers deployed to Vercel.

### Authentication

Two auth methods, checked in order:
1. **Bearer token** (API key): `Authorization: Bearer tb_xxxx` — look up
   `key_hash` in `api_keys` table, resolve `team_id`.
2. **Supabase session cookie**: For browser-based dashboard access. Resolved via
   Supabase middleware.

### POST /api/v1/upload

Accepts a `Catalog` JSON payload (the same shape produced by
`agent-table-brief`'s `scan_repository()`). Upserts the catalog and all briefs
for the team.

```
Request:  { catalog: Catalog }    (Catalog from agent-table-brief models)
Response: { catalog_id, brief_count, tables: string[] }
Scope:    write
```

Implementation:
1. Validate the Catalog JSON against the Pydantic schema.
2. Upsert into `catalogs` (keyed by `team_id + repo_key`).
3. Delete existing briefs for that catalog, insert new ones.
4. Populate the `fts` column (automatic via generated column).
5. Write audit log entry.

### GET /api/v1/catalogs

List all catalogs for the team.

```
Response: [{ id, repo_key, repo_root, project_type, brief_count, created_at }]
Scope:    read
```

### GET /api/v1/briefs/:table

Get a single brief by table name.

```
Query:    ?catalog_id=xxx (optional, defaults to latest)
Response: TableBrief JSON (same shape as CLI output)
Scope:    read
```

### GET /api/v1/search

Full-text search over briefs.

```
Query:    ?q=daily+active+users&limit=10&catalog_id=xxx
Response: { query, hits: [{ table, rank, brief }] }
Scope:    read
```

Implementation uses Postgres `ts_rank` with the `fts` generated column:

```sql
select table_name, ts_rank(fts, query) as rank, payload_json
from briefs, plainto_tsquery('english', $1) query
where team_id = $2 and fts @@ query
order by rank desc
limit $3
```

### POST /api/v1/compare

Compare two or more tables.

```
Request:  { tables: ["mart.dau", "mart.dau_all"], catalog_id?: string }
Response: CompareResult JSON (same shape as CLI output)
Scope:    read
```

### GET /api/v1/repos

List all repos (catalogs) for the team.

```
Response: [{ repo_key, repo_root, project_type, brief_count, created_at }]
Scope:    read
```

### POST /api/mcp

Hosted MCP endpoint using SSE transport. Exposes the same 5 tools as the
local MCP server (`search_tables`, `get_brief`, `compare_tables`,
`list_tables`, `list_repos`) but reads from Supabase instead of local SQLite.

Authenticated via API key in the `Authorization` header.

## Web Dashboard Pages

### / (Dashboard Home)
- Team overview: number of catalogs, total briefs, last scan timestamp.
- Quick search bar.
- Recent catalogs list.

### /catalogs
- Table listing all catalogs with repo name, project type, brief count, last
  updated.
- Click to view catalog detail.

### /catalogs/[id]
- Table of all briefs in the catalog: table name, purpose, confidence (as a
  colored badge), grain.
- Click a row to view brief detail.
- Search/filter within the catalog.

### /briefs/[table]
- Full brief detail view with all fields rendered.
- Confidence shown per-field with colored indicators.
- Evidence list with file paths and line ranges.
- Alternatives shown as clickable links to other briefs.
- Lineage mini-graph: derived_from (upstream) and downstream_usage.

### /search
- Full-text search input.
- Live results as the user types (debounced, calls /api/v1/search).
- Results show table name, purpose snippet, confidence, catalog source.

### /compare
- Multi-select tables (from a searchable dropdown).
- Side-by-side diff view highlighting diverging fields.
- Shared fields shown once, differences shown in colored columns.

### /settings
- Team name, slug.
- Danger zone: delete team.

### /settings/members
- List current members with role badges.
- Invite by email.
- Change role (owner, admin, member).
- Remove member.

### /settings/api-keys
- List existing API keys (show prefix + scope, never the full key).
- Create new key: name, scope (read/write/admin).
- Copy key on creation (shown once).
- Revoke key.

## CLI Integration (changes to agent-table-brief)

A thin `cloud_client.py` module is added to the open-source CLI repo. It handles
upload and download without importing any cloud-specific dependencies.

### New CLI flags

```
tablebrief scan path/to/repo --cloud              # scan locally, upload to cloud
tablebrief brief mart.dau --cloud                  # fetch from cloud instead of local
tablebrief search "daily active" --cloud           # search cloud catalog
```

### cloud_client.py (added to agent-table-brief, MIT)

```python
import httpx

CLOUD_API_URL = os.environ.get("TABLEBRIEF_CLOUD_URL", "https://tablebrief.dev")
CLOUD_API_KEY = os.environ.get("TABLEBRIEF_API_KEY")

def upload_catalog(catalog: Catalog) -> dict:
    resp = httpx.post(
        f"{CLOUD_API_URL}/api/v1/upload",
        json={"catalog": catalog.model_dump(mode="json")},
        headers={"Authorization": f"Bearer {CLOUD_API_KEY}"},
    )
    resp.raise_for_status()
    return resp.json()

def cloud_search(query: str, limit: int = 10) -> SearchResult:
    resp = httpx.get(
        f"{CLOUD_API_URL}/api/v1/search",
        params={"q": query, "limit": limit},
        headers={"Authorization": f"Bearer {CLOUD_API_KEY}"},
    )
    resp.raise_for_status()
    return SearchResult.model_validate(resp.json())

def cloud_brief(table: str) -> TableBrief:
    resp = httpx.get(
        f"{CLOUD_API_URL}/api/v1/briefs/{table}",
        headers={"Authorization": f"Bearer {CLOUD_API_KEY}"},
    )
    resp.raise_for_status()
    return TableBrief.model_validate(resp.json())
```

### Environment variables

```
TABLEBRIEF_CLOUD_URL=https://tablebrief.dev    # or self-hosted URL
TABLEBRIEF_API_KEY=tb_xxxxxxxxxxxxxxxxxxxx      # team API key
```

## Implementation Phases

### Phase 1 — Foundation (week 1)

| # | Task | Detail |
|---|------|--------|
| 1.1 | Scaffold monorepo | `npx create-turbo`, Next.js 15 app, Tailwind, shadcn/ui |
| 1.2 | Supabase project | Create project, connect to Vercel |
| 1.3 | Run migrations 001-006 | Teams, catalogs, briefs, API keys, audit, RLS |
| 1.4 | Auth pages | Login, signup, OAuth (Google) using Supabase Auth |
| 1.5 | Team creation flow | Create team on first login, team switcher in sidebar |
| 1.6 | Middleware | Supabase session validation, redirect unauthenticated |

### Phase 2 — Upload + Storage (week 2)

| # | Task | Detail |
|---|------|--------|
| 2.1 | POST /api/v1/upload | Accept Catalog JSON, upsert catalog + briefs |
| 2.2 | API key auth | Generate, hash (SHA-256), validate API keys |
| 2.3 | API key management page | Create, list, revoke keys |
| 2.4 | `cloud_client.py` in agent-table-brief | `upload_catalog()` function |
| 2.5 | `--cloud` flag on `scan` command | Scan locally, upload via cloud_client |
| 2.6 | Audit logging | Log uploads with user, team, catalog info |

### Phase 3 — Dashboard (week 3)

| # | Task | Detail |
|---|------|--------|
| 3.1 | Dashboard home | Team stats, recent catalogs, quick search |
| 3.2 | Catalogs list page | Table of catalogs with metadata |
| 3.3 | Catalog detail page | Brief table with search/filter |
| 3.4 | Brief detail page | Full brief rendering with evidence, lineage |
| 3.5 | Confidence badges | Color-coded per-field confidence indicators |
| 3.6 | Search page | Full-text search with live results |
| 3.7 | Compare page | Multi-select + side-by-side diff view |

### Phase 4 — API + Cloud CLI (week 4)

| # | Task | Detail |
|---|------|--------|
| 4.1 | GET /api/v1/catalogs | List catalogs |
| 4.2 | GET /api/v1/briefs/:table | Get single brief |
| 4.3 | GET /api/v1/search | Full-text search |
| 4.4 | POST /api/v1/compare | Compare tables |
| 4.5 | GET /api/v1/repos | List repos |
| 4.6 | `--cloud` flag on `brief`, `search` | Fetch from cloud API |
| 4.7 | Rate limiting | Vercel Edge middleware, per API key |

### Phase 5 — Hosted MCP + Team Management (week 5)

| # | Task | Detail |
|---|------|--------|
| 5.1 | POST /api/mcp | MCP endpoint (SSE transport) with API key auth |
| 5.2 | MCP tool handlers | Same 5 tools, backed by Supabase queries |
| 5.3 | Team member invite | Email invite flow |
| 5.4 | Role management | Owner/admin/member RBAC |
| 5.5 | Settings page | Team settings, danger zone |
| 5.6 | Connection guide | In-app instructions for Cursor, Claude Desktop |

### Phase 6 — Polish + Launch (week 6)

| # | Task | Detail |
|---|------|--------|
| 6.1 | Landing page | Marketing page at tablebrief.dev |
| 6.2 | Onboarding flow | First scan guide, API key setup wizard |
| 6.3 | Error handling | Structured errors on all API routes |
| 6.4 | Loading states | Skeletons, optimistic updates |
| 6.5 | Mobile responsive | Dashboard works on tablet/mobile |
| 6.6 | E2E tests | Playwright tests for critical flows |
| 6.7 | Deploy to production | Vercel production, custom domain |

## AGENTS.md for tablebrief-cloud

The following should be placed as `AGENTS.md` in the `tablebrief-cloud` repo:

```markdown
# AGENTS.md

## Project overview

tablebrief-cloud is the SaaS layer for agent-table-brief. It provides team-based
sharing of table catalogs via a web dashboard, REST API, and hosted MCP endpoint.

## Tech stack

- Next.js 15 (App Router) on Vercel
- Supabase (Postgres, Auth, RLS)
- Tailwind CSS + shadcn/ui
- Turborepo monorepo
- TypeScript

## Dependencies on agent-table-brief

This project depends on the open-source `agent-table-brief` Python package for
its Pydantic models and inference logic. Key types:

- `Catalog`: repo_root, project_type, generated_at, version, briefs[]
- `TableBrief`: table, purpose, grain, primary_keys, derived_from,
  filters_or_exclusions, freshness_hints, downstream_usage, alternatives,
  confidence, field_confidence, evidence[]
- `SearchResult`: query, hits[] (each hit has table, rank, brief)
- `CompareResult`: tables[], differences{}
- `ScanResult`: repo_key, repo_root, effective_root, project_type, scan_id,
  status, reused, brief_count, tables[], generated_at
- `EvidenceRef`: file, start_line, end_line, kind

The API accepts and returns JSON matching these Pydantic schemas exactly.

## Running locally

npm install
npx supabase start       # local Supabase
npm run dev              # Next.js dev server at localhost:3000

## Environment variables

NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from supabase start>
SUPABASE_SERVICE_ROLE_KEY=<from supabase start>

## Database

Migrations are in supabase/migrations/. Apply with:

npx supabase db push

Key tables: teams, team_members, catalogs, briefs, api_keys, audit_log.
All tables have RLS enabled. Policies enforce team-scoped access.

## API routes

POST /api/v1/upload          Upload a Catalog JSON (scope: write)
GET  /api/v1/catalogs        List catalogs (scope: read)
GET  /api/v1/briefs/:table   Get a brief (scope: read)
GET  /api/v1/search?q=...    Full-text search (scope: read)
POST /api/v1/compare         Compare tables (scope: read)
GET  /api/v1/repos           List repos (scope: read)
POST /api/mcp                Hosted MCP endpoint (scope: read)

Auth: Bearer token (API key) or Supabase session cookie.
```

## Key Design Decisions

### Catalog JSON is the contract

The `Catalog` Pydantic model from `agent-table-brief` is the data contract
between the CLI and the cloud. The upload endpoint accepts `Catalog` JSON
verbatim. This means:

- No schema translation layer needed.
- CLI upgrades that add new fields to `TableBrief` automatically flow through
  to the cloud (stored as JSONB).
- The cloud never needs to understand inference logic.

### JSONB for brief storage

Briefs are stored as `payload_json jsonb` (the full `TableBrief` serialized).
Indexed columns (`table_name`, `purpose`, `grain`, `confidence`) are extracted
for queries and FTS. This gives flexibility: if the `TableBrief` schema adds
fields, the JSONB column stores them without a migration.

### Postgres FTS instead of external search

Postgres `tsvector` with weighted columns (table name = A, purpose = B,
grain = C, filters = D) provides good-enough search with zero external
dependencies. Upgrade to pgvector + embeddings later if semantic search is
needed.

### API keys are hashed

API keys are generated as `tb_<32 random hex chars>`. Only the SHA-256 hash is
stored. The key prefix (`tb_xxxx`) is stored for identification in the UI.
The full key is shown once on creation and never again.
