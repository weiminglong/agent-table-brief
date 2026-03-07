from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from agent_table_brief.models import (
    Catalog,
    MaintenanceResult,
    RepoSummary,
    ScanResult,
    SearchHit,
    SearchResult,
    TableBrief,
)
from agent_table_brief.repository import (
    _discover_metadata_yaml_files,
    _discover_model_files,
    _resolve_scan_target,
)

RETENTION_PER_REPO = 3
SQLITE_TIMEOUT_SECONDS = 5.0


class RepoNotScannedError(Exception):
    pass


class RepoAmbiguousError(Exception):
    pass


@dataclass(frozen=True)
class RepoIdentity:
    repo_key: str
    repo_root: str
    effective_root: str
    git_remote_url: str | None
    git_root: str | None
    commit_sha: str | None
    subpath: str


def resolve_store_path(path: Path | None = None) -> Path:
    if path is not None:
        return path.resolve()
    env_home = os.environ.get("TABLEBRIEF_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve() / "store.db"
    return _default_tablebrief_home() / "store.db"


class CatalogStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def store_scan(self, catalog: Catalog) -> ScanResult:
        identity = _build_repo_identity(Path(catalog.repo_root))
        fingerprint, file_hashes = _compute_repo_fingerprint(
            Path(catalog.repo_root), catalog.project_type
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            repo_id = self._upsert_repo(connection, identity, catalog.project_type)
            existing_row = connection.execute(
                """
                SELECT scans.id, scans.generated_at, scans.brief_count
                FROM scans
                WHERE scans.repo_id = ? AND scans.repo_fingerprint = ? AND scans.scanner_version = ?
                  AND scans.status = 'complete'
                """,
                (repo_id, fingerprint, catalog.version),
            ).fetchone()
            if existing_row is not None:
                existing_scan_id = int(existing_row["id"])
                self._set_active_repo_scan(
                    connection,
                    repo_id,
                    existing_scan_id,
                    identity,
                    catalog.project_type,
                )
                generated_at = _parse_timestamp(existing_row["generated_at"])
                table_names = self._load_table_names(connection, existing_scan_id)
                return ScanResult(
                    repo_key=identity.repo_key,
                    repo_root=identity.repo_root,
                    effective_root=identity.effective_root,
                    project_type=catalog.project_type,
                    scan_id=existing_scan_id,
                    status="complete",
                    reused=True,
                    brief_count=int(existing_row["brief_count"]),
                    tables=table_names,
                    generated_at=generated_at,
                )

            cursor = connection.execute(
                """
                INSERT INTO scans (
                    repo_id,
                    generated_at,
                    scanner_version,
                    repo_fingerprint,
                    commit_sha,
                    status,
                    file_count,
                    brief_count,
                    catalog_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    catalog.generated_at.isoformat(),
                    catalog.version,
                    fingerprint,
                    identity.commit_sha,
                    "pending",
                    len(file_hashes),
                    len(catalog.briefs),
                    catalog.version,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Scan insert did not return a row id")
            scan_id = int(cursor.lastrowid)
            self._insert_scan_files(connection, scan_id, file_hashes)
            self._insert_briefs(connection, scan_id, catalog.briefs)
            connection.execute(
                "UPDATE scans SET status = ? WHERE id = ?",
                ("complete", scan_id),
            )
            self._set_active_repo_scan(connection, repo_id, scan_id, identity, catalog.project_type)
            self._prune_old_scans(connection, repo_id)
        return ScanResult(
            repo_key=identity.repo_key,
            repo_root=identity.repo_root,
            effective_root=identity.effective_root,
            project_type=catalog.project_type,
            scan_id=scan_id,
            status="complete",
            reused=False,
            brief_count=len(catalog.briefs),
            tables=sorted(b.table for b in catalog.briefs),
            generated_at=catalog.generated_at,
        )

    def load_catalog(self, repo_path: Path | None = None) -> Catalog:
        repo_row = self._resolve_repo_row(repo_path)
        scan_row = self._active_scan_row(repo_row["id"])
        briefs = self._load_briefs(int(scan_row["id"]))
        return Catalog(
            repo_root=str(repo_row["effective_root"]),
            project_type=str(repo_row["project_type"]),
            generated_at=_parse_timestamp(str(scan_row["generated_at"])),
            version=str(scan_row["catalog_version"]),
            briefs=briefs,
        )

    def load_brief(self, table_name: str, repo_path: Path | None = None) -> TableBrief:
        repo_row = self._resolve_repo_row(repo_path)
        scan_row = self._active_scan_row(repo_row["id"])
        scan_id = int(scan_row["id"])
        connection = self._connect()
        try:
            exact_row = connection.execute(
                "SELECT payload_json FROM briefs WHERE scan_id = ? AND table_name = ?",
                (scan_id, table_name),
            ).fetchone()
            if exact_row is not None:
                return TableBrief.model_validate_json(str(exact_row["payload_json"]))
            short_rows = connection.execute(
                "SELECT table_name, payload_json FROM briefs WHERE scan_id = ? AND short_name = ?",
                (scan_id, table_name),
            ).fetchall()
            if len(short_rows) == 1:
                return TableBrief.model_validate_json(str(short_rows[0]["payload_json"]))
            if len(short_rows) > 1:
                options = ", ".join(sorted(str(row["table_name"]) for row in short_rows))
                raise ValueError(f"Table name is ambiguous: {table_name}. Matches: {options}")
            raise KeyError(f"Table not found in catalog: {table_name}")
        finally:
            connection.close()

    def search(
        self,
        query: str,
        repo_path: Path | None = None,
        limit: int = 10,
    ) -> SearchResult:
        repo_row = self._resolve_repo_row(repo_path)
        scan_row = self._active_scan_row(repo_row["id"])
        scan_id = int(scan_row["id"])
        escaped_query = _escape_fts_query(query)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    briefs_fts.table_name,
                    bm25(briefs_fts) AS rank,
                    briefs.payload_json
                FROM briefs_fts
                JOIN briefs
                    ON briefs.table_name = briefs_fts.table_name
                    AND briefs.scan_id = ?
                WHERE briefs_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (scan_id, escaped_query, limit),
            ).fetchall()
        hits = [
            SearchHit(
                table=str(row["table_name"]),
                rank=-float(row["rank"]),
                brief=TableBrief.model_validate_json(str(row["payload_json"])),
            )
            for row in rows
        ]
        return SearchResult(query=query, hits=hits)

    def list_repos(self) -> list[RepoSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    repos.repo_key,
                    repos.repo_root,
                    repos.effective_root,
                    repos.project_type,
                    scans.brief_count,
                    scans.generated_at
                FROM repos
                LEFT JOIN scans ON scans.id = repos.active_scan_id
                ORDER BY repos.updated_at DESC, repos.repo_key ASC
                """
            ).fetchall()
        summaries: list[RepoSummary] = []
        for row in rows:
            if row["generated_at"] is None:
                continue
            summaries.append(
                RepoSummary(
                    repo_key=str(row["repo_key"]),
                    repo_root=str(row["repo_root"]),
                    effective_root=str(row["effective_root"]),
                    project_type=str(row["project_type"]),
                    brief_count=int(row["brief_count"]),
                    generated_at=_parse_timestamp(str(row["generated_at"])),
                )
            )
        return summaries

    def gc(self) -> MaintenanceResult:
        with self._connect() as connection:
            repo_rows = connection.execute("SELECT id FROM repos").fetchall()
            removed_total = 0
            for repo_row in repo_rows:
                removed_total += self._prune_old_scans(connection, int(repo_row["id"]))
        return MaintenanceResult(repos_considered=len(repo_rows), scans_removed=removed_total)

    def vacuum(self) -> MaintenanceResult:
        with self._connect() as connection:
            repo_count = int(connection.execute("SELECT COUNT(*) FROM repos").fetchone()[0])
            connection.execute("VACUUM")
        return MaintenanceResult(repos_considered=repo_count, scans_removed=0)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=SQLITE_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_key TEXT NOT NULL UNIQUE,
                    repo_root TEXT NOT NULL,
                    effective_root TEXT NOT NULL,
                    project_type TEXT NOT NULL,
                    git_remote_url TEXT,
                    git_root TEXT,
                    subpath TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    active_scan_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                    generated_at TEXT NOT NULL,
                    scanner_version TEXT NOT NULL,
                    repo_fingerprint TEXT NOT NULL,
                    commit_sha TEXT,
                    status TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    brief_count INTEGER NOT NULL,
                    catalog_version TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS briefs (
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    table_name TEXT NOT NULL,
                    short_name TEXT NOT NULL,
                    purpose TEXT,
                    grain TEXT,
                    confidence REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (scan_id, table_name)
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    table_name TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    file TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    kind TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scan_files (
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    relative_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (scan_id, relative_path)
                );

                CREATE INDEX IF NOT EXISTS idx_repos_effective_root ON repos(effective_root);
                CREATE INDEX IF NOT EXISTS idx_scans_repo_generated_at
                ON scans(repo_id, generated_at DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_scans_repo_fingerprint
                ON scans(repo_id, repo_fingerprint, scanner_version);
                CREATE INDEX IF NOT EXISTS idx_briefs_scan_short_name
                ON briefs(scan_id, short_name);
                CREATE INDEX IF NOT EXISTS idx_evidence_scan_table ON evidence(scan_id, table_name);

                CREATE VIRTUAL TABLE IF NOT EXISTS briefs_fts USING fts5(
                    table_name,
                    purpose,
                    grain,
                    filters,
                    alternatives,
                    tokenize='unicode61'
                );
                """
            )

    def _upsert_repo(
        self,
        connection: sqlite3.Connection,
        identity: RepoIdentity,
        project_type: str,
    ) -> int:
        existing = connection.execute(
            "SELECT id FROM repos WHERE repo_key = ?",
            (identity.repo_key,),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        timestamp = _isoformat_now()
        cursor = connection.execute(
            """
            INSERT INTO repos (
                repo_key,
                repo_root,
                effective_root,
                project_type,
                git_remote_url,
                git_root,
                subpath,
                created_at,
                updated_at,
                active_scan_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                identity.repo_key,
                identity.repo_root,
                identity.effective_root,
                project_type,
                identity.git_remote_url,
                identity.git_root,
                identity.subpath,
                timestamp,
                timestamp,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Repo insert did not return a row id")
        return int(cursor.lastrowid)

    def _insert_scan_files(
        self,
        connection: sqlite3.Connection,
        scan_id: int,
        file_hashes: list[tuple[str, str]],
    ) -> None:
        connection.executemany(
            "INSERT INTO scan_files (scan_id, relative_path, content_hash) VALUES (?, ?, ?)",
            [(scan_id, relative_path, content_hash) for relative_path, content_hash in file_hashes],
        )

    def _insert_briefs(
        self,
        connection: sqlite3.Connection,
        scan_id: int,
        briefs: list[TableBrief],
    ) -> None:
        brief_rows: list[tuple[int, str, str, str | None, str | None, float, str]] = []
        evidence_rows: list[tuple[int, str, str, str, int, int, str]] = []
        for brief in briefs:
            short_name = brief.table.split(".")[-1]
            brief_rows.append(
                (
                    scan_id,
                    brief.table,
                    short_name,
                    brief.purpose,
                    brief.grain,
                    brief.confidence,
                    brief.model_dump_json(indent=None),
                )
            )
            grouped_evidence = brief.field_evidence or {"": brief.evidence}
            for field_name, evidence_list in grouped_evidence.items():
                for evidence in evidence_list:
                    evidence_rows.append(
                        (
                            scan_id,
                            brief.table,
                            field_name,
                            evidence.file,
                            evidence.start_line,
                            evidence.end_line,
                            evidence.kind,
                        )
                    )
        connection.executemany(
            """
            INSERT INTO briefs (
                scan_id,
                table_name,
                short_name,
                purpose,
                grain,
                confidence,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            brief_rows,
        )
        connection.executemany(
            """
            INSERT INTO evidence (
                scan_id,
                table_name,
                field_name,
                file,
                start_line,
                end_line,
                kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            evidence_rows,
        )
        fts_rows: list[tuple[str, str | None, str | None, str, str]] = []
        for brief in briefs:
            fts_rows.append((
                brief.table,
                brief.purpose,
                brief.grain,
                ", ".join(brief.filters_or_exclusions),
                ", ".join(brief.alternatives),
            ))
        connection.executemany(
            "INSERT INTO briefs_fts (table_name, purpose, grain, filters, alternatives)"
            " VALUES (?, ?, ?, ?, ?)",
            fts_rows,
        )

    def _set_active_repo_scan(
        self,
        connection: sqlite3.Connection,
        repo_id: int,
        scan_id: int,
        identity: RepoIdentity,
        project_type: str,
    ) -> None:
        updated_at = _isoformat_now()
        connection.execute(
            """
            UPDATE repos
            SET
                repo_root = ?,
                effective_root = ?,
                project_type = ?,
                git_remote_url = ?,
                git_root = ?,
                subpath = ?,
                updated_at = ?,
                active_scan_id = ?
            WHERE id = ?
            """,
            (
                identity.repo_root,
                identity.effective_root,
                project_type,
                identity.git_remote_url,
                identity.git_root,
                identity.subpath,
                updated_at,
                scan_id,
                repo_id,
            ),
        )

    def _prune_old_scans(self, connection: sqlite3.Connection, repo_id: int) -> int:
        rows = connection.execute(
            """
            SELECT id
            FROM scans
            WHERE repo_id = ? AND status = 'complete'
            ORDER BY generated_at DESC, id DESC
            """,
            (repo_id,),
        ).fetchall()
        removable = [int(row["id"]) for row in rows[RETENTION_PER_REPO:]]
        if not removable:
            return 0
        placeholders = ", ".join("?" for _ in removable)
        connection.execute(
            f"DELETE FROM scans WHERE id IN ({placeholders})",
            removable,
        )
        return len(removable)

    def _resolve_repo_row(self, repo_path: Path | None) -> sqlite3.Row:
        candidate = (repo_path or Path.cwd()).resolve()
        with self._connect() as connection:
            repo_rows = connection.execute(
                """
                SELECT id, repo_key, repo_root, effective_root, project_type, active_scan_id
                FROM repos
                ORDER BY LENGTH(effective_root) DESC, repo_key ASC
                """
            ).fetchall()
        matching_rows = [
            row
            for row in repo_rows
            if candidate == Path(str(row["effective_root"]))
            or candidate.is_relative_to(Path(str(row["effective_root"])))
        ]
        if len(matching_rows) == 1:
            row = matching_rows[0]
            if row["active_scan_id"] is None:
                raise RepoNotScannedError(f"No active scan found for repo: {row['effective_root']}")
            return cast(sqlite3.Row, row)
        if len(matching_rows) > 1:
            matches = ", ".join(str(row["effective_root"]) for row in matching_rows)
            raise RepoAmbiguousError(f"Repository is ambiguous for {candidate}. Matches: {matches}")

        try:
            identity = _build_repo_identity(candidate)
        except ValueError as exc:
            raise RepoNotScannedError(f"Repository has not been scanned: {candidate}") from exc
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, repo_key, repo_root, effective_root, project_type, active_scan_id
                FROM repos
                WHERE repo_key = ?
                """,
                (identity.repo_key,),
            ).fetchone()
        if row is None or row["active_scan_id"] is None:
            raise RepoNotScannedError(f"Repository has not been scanned: {candidate}")
        return cast(sqlite3.Row, row)

    def _active_scan_row(self, repo_id: int) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT scans.id, scans.generated_at, scans.catalog_version
                FROM scans
                JOIN repos ON repos.active_scan_id = scans.id
                WHERE repos.id = ?
                """,
                (repo_id,),
            ).fetchone()
        if row is None:
            raise RepoNotScannedError(f"No active scan found for repo id: {repo_id}")
        return cast(sqlite3.Row, row)

    def _load_table_names(
        self, connection: sqlite3.Connection, scan_id: int
    ) -> list[str]:
        rows = connection.execute(
            "SELECT table_name FROM briefs WHERE scan_id = ? ORDER BY table_name ASC",
            (scan_id,),
        ).fetchall()
        return [str(row["table_name"]) for row in rows]

    def _load_briefs(self, scan_id: int) -> list[TableBrief]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM briefs
                WHERE scan_id = ?
                ORDER BY table_name ASC
                """,
                (scan_id,),
            ).fetchall()
        return [TableBrief.model_validate_json(str(row["payload_json"])) for row in rows]


def _build_repo_identity(path: Path) -> RepoIdentity:
    effective_root = _resolve_scan_target(path, "auto").root
    git_top = _run_git(effective_root, "rev-parse", "--show-toplevel")
    git_root = Path(git_top).resolve() if git_top else None
    git_remote_url = _run_git(effective_root, "config", "--get", "remote.origin.url")
    commit_sha = _run_git(effective_root, "rev-parse", "HEAD")
    subpath = (
        effective_root.relative_to(git_root).as_posix()
        if git_root is not None and effective_root != git_root
        else "."
    )
    repo_root = str(git_root if git_root is not None else effective_root)
    stable_parts = [subpath]
    if git_remote_url:
        stable_parts.insert(0, git_remote_url)
    elif git_root is not None:
        stable_parts.insert(0, str(git_root))
    else:
        stable_parts.insert(0, str(effective_root))
    stable_identity = "|".join(stable_parts)
    repo_key = hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()
    return RepoIdentity(
        repo_key=repo_key,
        repo_root=repo_root,
        effective_root=str(effective_root),
        git_remote_url=git_remote_url,
        git_root=str(git_root) if git_root is not None else None,
        commit_sha=commit_sha,
        subpath=subpath,
    )


def _compute_repo_fingerprint(root: Path, project_type: str) -> tuple[str, list[tuple[str, str]]]:
    scan_target = _resolve_scan_target(root, project_type)
    files = _input_files(scan_target.root, scan_target.project_type)
    file_hashes: list[tuple[str, str]] = []
    digest = hashlib.sha256()
    digest.update(scan_target.project_type.encode("utf-8"))
    for path in files:
        relative_path = path.relative_to(scan_target.root).as_posix()
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        file_hashes.append((relative_path, content_hash))
        digest.update(relative_path.encode("utf-8"))
        digest.update(content_hash.encode("utf-8"))
    return digest.hexdigest(), file_hashes


def _input_files(root: Path, project_type: str) -> list[Path]:
    files: dict[str, Path] = {}

    def add_path(path: Path) -> None:
        files[path.resolve().as_posix()] = path

    for path in _discover_model_files(root, project_type):
        add_path(path)
    for path in _discover_metadata_yaml_files(root):
        add_path(path)
    if project_type == "dbt":
        dbt_project = root / "dbt_project.yml"
        if dbt_project.exists():
            add_path(dbt_project)
        manifest_path = root / "target" / "manifest.json"
        if manifest_path.exists():
            add_path(manifest_path)
    return sorted(files.values())


def _default_tablebrief_home() -> Path:
    home = Path.home()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "tablebrief"
        return home / "AppData" / "Local" / "tablebrief"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "tablebrief"
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "tablebrief"
    return home / ".local" / "state" / "tablebrief"


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _isoformat_now() -> str:
    return datetime.now(UTC).isoformat()


def _escape_fts_query(query: str) -> str:
    tokens = query.split()
    escaped: list[str] = []
    for token in tokens:
        cleaned = re.sub(r"[^\w]", "", token)
        if cleaned:
            escaped.append(f'"{cleaned}"')
    return " OR ".join(escaped) if escaped else '""'


def _run_git(path: Path, *args: str) -> str | None:
    process = subprocess.run(
        ["git", "-C", str(path), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        return None
    value = process.stdout.strip()
    return value or None
