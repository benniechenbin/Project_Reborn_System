import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    PromptMetadata,
)
from reborn_core.config import Settings, get_settings
from reborn_core.observability import logger
from reborn_core.runtime import TaskRecord, TaskStatus


class ClosingConnection(sqlite3.Connection):
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()
        return False


class DBManager:
    """提供仅向前迁移数据库结构的 SQLite 仓储。"""

    def __init__(
        self,
        app_settings: Settings | None = None,
        db_path: Path | None = None,
    ) -> None:
        settings = app_settings or get_settings()
        self.db_path = db_path or settings.resolved_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30,
            factory=ClosingConnection,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def migrate(self) -> None:
        migrations = (
            self._migration_001_sync_history,
            self._migration_002_identity_snapshots,
            self._migration_003_background_tasks,
            self._migration_004_backup_and_audit,
        )
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                row["version"] for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for version, migration in enumerate(migrations, start=1):
                if version in applied:
                    continue
                migration(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )
            conn.commit()
        logger.info("SQLite migrations are current at version {}", len(migrations))

    def save_sync_record(self, metrics: dict[str, float | int | str | None]) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_history
                    (sync_time, audio_duration, notes_count, word_count, generation_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    metrics.get("sync_time", datetime.now(UTC).isoformat()),
                    metrics.get("audio_duration", 0),
                    metrics.get("notes_count", 0),
                    metrics.get("word_count", 0),
                    metrics.get("generation_id"),
                ),
            )
            conn.commit()

    def create_identity_snapshot(self, snapshot: IdentitySnapshot) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO identity_snapshots (
                    snapshot_id, parent_snapshot_id, content, content_sha256, source_ids_json,
                    model_provider, model_name, model_base_url, prompt_id, prompt_version,
                    prompt_sha256, generation_params_json, status, created_at, reviewed_at,
                    reviewed_by, review_note, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.parent_snapshot_id,
                    snapshot.content,
                    snapshot.content_sha256,
                    json.dumps(snapshot.source_ids, ensure_ascii=False),
                    snapshot.model.provider,
                    snapshot.model.model_name,
                    snapshot.model.base_url,
                    snapshot.prompt.prompt_id,
                    snapshot.prompt.version,
                    snapshot.prompt.sha256,
                    json.dumps(snapshot.generation_params, ensure_ascii=False),
                    snapshot.status.value,
                    snapshot.created_at,
                    snapshot.reviewed_at,
                    snapshot.reviewed_by,
                    snapshot.review_note,
                    int(snapshot.active),
                ),
            )
            conn.commit()

    def get_identity_snapshot(self, snapshot_id: str) -> IdentitySnapshot | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM identity_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        return _identity_from_row(row) if row else None

    def get_active_identity_snapshot(self) -> IdentitySnapshot | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM identity_snapshots WHERE active = 1 LIMIT 1"
            ).fetchone()
        return _identity_from_row(row) if row else None

    def list_identity_snapshots(
        self,
        status: IdentitySnapshotStatus | None = None,
        limit: int = 20,
    ) -> list[IdentitySnapshot]:
        sql = "SELECT * FROM identity_snapshots"
        params: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status.value)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_identity_from_row(row) for row in rows]

    def review_identity_snapshot(
        self,
        snapshot_id: str,
        status: IdentitySnapshotStatus,
        reviewed_by: str,
        review_note: str | None = None,
    ) -> IdentitySnapshot:
        if status not in {IdentitySnapshotStatus.APPROVED, IdentitySnapshotStatus.REJECTED}:
            raise ValueError("Review status must be approved or rejected")
        reviewed_at = datetime.now(UTC).isoformat()
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM identity_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            if row is None:
                raise LookupError(f"Identity snapshot not found: {snapshot_id}")
            if status is IdentitySnapshotStatus.APPROVED:
                conn.execute("UPDATE identity_snapshots SET active = 0 WHERE active = 1")
            conn.execute(
                """
                UPDATE identity_snapshots
                SET status = ?, reviewed_at = ?, reviewed_by = ?, review_note = ?, active = ?
                WHERE snapshot_id = ?
                """,
                (
                    status.value,
                    reviewed_at,
                    reviewed_by,
                    review_note,
                    int(status is IdentitySnapshotStatus.APPROVED),
                    snapshot_id,
                ),
            )
        reviewed = self.get_identity_snapshot(snapshot_id)
        if reviewed is None:
            raise LookupError(f"Identity snapshot disappeared after review: {snapshot_id}")
        return reviewed

    def create_task(self, task: TaskRecord) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO background_tasks
                    (task_id, kind, status, created_at, updated_at, result_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.kind,
                    task.status.value,
                    task.created_at,
                    task.updated_at,
                    task.result_json,
                    task.error,
                ),
            )
            conn.commit()

    def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result_json: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE background_tasks
                SET status = ?, updated_at = ?, result_json = ?, error = ?
                WHERE task_id = ?
                """,
                (status.value, datetime.now(UTC).isoformat(), result_json, error, task_id),
            )
            conn.commit()

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM background_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return TaskRecord(
            task_id=row["task_id"],
            kind=row["kind"],
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            result_json=row["result_json"],
            error=row["error"],
        )

    def mark_unfinished_tasks_failed(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE background_tasks
                SET status = ?, updated_at = ?, error = ?
                WHERE status IN (?, ?)
                """,
                (
                    TaskStatus.FAILED.value,
                    datetime.now(UTC).isoformat(),
                    "Process restarted before the task completed",
                    TaskStatus.QUEUED.value,
                    TaskStatus.RUNNING.value,
                ),
            )
            conn.commit()
            return cursor.rowcount

    def save_backup_record(
        self,
        backup_id: str,
        path: str,
        sha256: str,
        encrypted: bool,
        status: str,
        detail: str | None = None,
    ) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO backup_records
                    (backup_id, path, sha256, encrypted, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backup_id,
                    path,
                    sha256,
                    int(encrypted),
                    status,
                    detail,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

    def append_audit_event(
        self,
        action: str,
        resource: str,
        actor_id: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_events
                    (event_id, occurred_at, actor_id, action, resource, outcome, details_json)
                VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    actor_id,
                    action,
                    resource,
                    outcome,
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )
            conn.commit()

    @staticmethod
    def _migration_001_sync_history(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time TEXT NOT NULL,
                audio_duration REAL NOT NULL DEFAULT 0,
                notes_count INTEGER NOT NULL DEFAULT 0,
                word_count INTEGER NOT NULL DEFAULT 0,
                generation_id TEXT
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(sync_history)")}
        if "generation_id" not in columns:
            conn.execute("ALTER TABLE sync_history ADD COLUMN generation_id TEXT")

    @staticmethod
    def _migration_002_identity_snapshots(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS identity_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                parent_snapshot_id TEXT,
                content TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                model_provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_base_url TEXT,
                prompt_id TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                prompt_sha256 TEXT NOT NULL,
                generation_params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by TEXT,
                review_note TEXT,
                active INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_identity_status ON identity_snapshots(status, created_at)"
        )

    @staticmethod
    def _migration_003_background_tasks(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS background_tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result_json TEXT,
                error TEXT
            )
            """
        )

    @staticmethod
    def _migration_004_backup_and_audit(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backup_records (
                backup_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                encrypted INTEGER NOT NULL,
                status TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                outcome TEXT NOT NULL,
                details_json TEXT NOT NULL
            )
            """
        )


def _identity_from_row(row: sqlite3.Row) -> IdentitySnapshot:
    return IdentitySnapshot(
        snapshot_id=row["snapshot_id"],
        parent_snapshot_id=row["parent_snapshot_id"],
        content=row["content"],
        content_sha256=row["content_sha256"],
        source_ids=tuple(json.loads(row["source_ids_json"])),
        model=ModelMetadata(
            provider=row["model_provider"],
            model_name=row["model_name"],
            base_url=row["model_base_url"],
        ),
        prompt=PromptMetadata(
            prompt_id=row["prompt_id"],
            version=row["prompt_version"],
            sha256=row["prompt_sha256"],
        ),
        generation_params=json.loads(row["generation_params_json"]),
        status=IdentitySnapshotStatus(row["status"]),
        created_at=row["created_at"],
        reviewed_at=row["reviewed_at"],
        reviewed_by=row["reviewed_by"],
        review_note=row["review_note"],
        active=bool(row["active"]),
    )
