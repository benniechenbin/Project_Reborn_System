import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    PromptMetadata,
    SyncHistoryEntry,
)
from reborn_core.runtime import TaskRecord, TaskStatus

from .core import SQLiteDatabase


class SQLiteSyncHistoryRepository:
    """Persists knowledge synchronization metrics in SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save_sync_record(self, metrics: dict[str, float | int | str | None]) -> None:
        with self.database.get_connection() as conn:
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

    def list_sync_history(self) -> list[SyncHistoryEntry]:
        with self.database.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT sync_time, audio_duration, notes_count, word_count, generation_id
                FROM sync_history
                ORDER BY sync_time ASC
                """
            ).fetchall()
        return [
            SyncHistoryEntry(
                sync_time=str(row["sync_time"]),
                audio_duration=float(row["audio_duration"]),
                notes_count=int(row["notes_count"]),
                word_count=int(row["word_count"]),
                generation_id=row["generation_id"],
            )
            for row in rows
        ]


class SQLiteIdentitySnapshotRepository:
    """Persists governed identity snapshots in SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create_identity_snapshot(self, snapshot: IdentitySnapshot) -> None:
        with self.database.get_connection() as conn:
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
        with self.database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM identity_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        return _identity_from_row(row) if row else None

    def get_active_identity_snapshot(self) -> IdentitySnapshot | None:
        with self.database.get_connection() as conn:
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
        with self.database.get_connection() as conn:
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
        with self.database.transaction() as conn:
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


class SQLiteTaskRepository:
    """Persists background task state in SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create_task(self, task: TaskRecord) -> None:
        with self.database.get_connection() as conn:
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
        with self.database.get_connection() as conn:
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
        with self.database.get_connection() as conn:
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

    def has_active_task_of_kind(self, kind: str) -> bool:
        with self.database.get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM background_tasks
                WHERE kind = ? AND status IN (?, ?)
                LIMIT 1
                """,
                (kind, TaskStatus.QUEUED.value, TaskStatus.RUNNING.value),
            ).fetchone()
        return row is not None

    def mark_unfinished_tasks_failed(self) -> int:
        with self.database.get_connection() as conn:
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


class SQLiteBackupRecordRepository:
    """Persists backup and recovery-drill records in SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save_backup_record(
        self,
        backup_id: str,
        path: str,
        sha256: str,
        encrypted: bool,
        status: str,
        detail: str | None = None,
    ) -> None:
        with self.database.get_connection() as conn:
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


class SQLiteAuditRepository:
    """Appends access-policy audit events to SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def append_audit_event(
        self,
        action: str,
        resource: str,
        actor_id: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.database.get_connection() as conn:
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
