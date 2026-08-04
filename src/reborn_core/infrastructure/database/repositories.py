import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    PromptMetadata,
    SensitivityLevel,
    SourceArtifact,
    SourceArtifactType,
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


class SQLiteSourceArtifactRepository:
    """Persists auditable source artifacts in SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create_source_artifact(self, artifact: SourceArtifact) -> None:
        with self.database.transaction() as conn:
            conn.execute(
                """
                INSERT INTO source_artifacts (
                    artifact_id, artifact_type, storage_path, file_size_bytes,
                    content_sha256, authorization_purpose, authorized_target,
                    sensitivity_level, captured_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.artifact_type.value,
                    artifact.storage_path,
                    artifact.file_size_bytes,
                    artifact.content_sha256,
                    artifact.authorization_purpose,
                    artifact.authorized_target,
                    artifact.sensitivity_level.value,
                    artifact.captured_at,
                    json.dumps(artifact.metadata, ensure_ascii=False, separators=(",", ":")),
                ),
            )

    def get_source_artifact(self, artifact_id: str) -> SourceArtifact | None:
        with self.database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM source_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return _source_artifact_from_row(row) if row is not None else None

    def list_source_artifacts(
        self,
        artifact_type: SourceArtifactType | None = None,
        limit: int = 20,
    ) -> list[SourceArtifact]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        query = "SELECT * FROM source_artifacts"
        params: list[Any] = []
        if artifact_type is not None:
            query += " WHERE artifact_type = ?"
            params.append(artifact_type.value)
        query += " ORDER BY captured_at DESC, artifact_id DESC LIMIT ?"
        params.append(limit)
        with self.database.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_source_artifact_from_row(row) for row in rows]


class SQLiteTaskRepository:
    """Persists and atomically dispatches background tasks in SQLite."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def enqueue_task(
        self,
        task: TaskRecord,
        *,
        allow_parallel: bool = False,
    ) -> None:
        with self.database.transaction() as conn:
            if not allow_parallel:
                active = conn.execute(
                    """
                    SELECT task_id FROM background_tasks
                    WHERE kind = ? AND status IN (?, ?)
                    LIMIT 1
                    """,
                    (task.kind, TaskStatus.QUEUED.value, TaskStatus.RUNNING.value),
                ).fetchone()
                if active is not None:
                    raise ValueError(f"A background task of kind '{task.kind}' is already running")
            conn.execute(
                """
                INSERT INTO background_tasks (
                    task_id, kind, status, created_at, updated_at,
                    payload_json, result_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.kind,
                    task.status.value,
                    task.created_at,
                    task.updated_at,
                    task.payload_json,
                    task.result_json,
                    task.error,
                ),
            )

    def claim_next_queued_task(self) -> TaskRecord | None:
        with self.database.transaction() as conn:
            row = conn.execute(
                """
                SELECT task_id FROM background_tasks
                WHERE status = ?
                ORDER BY created_at ASC, task_id ASC
                LIMIT 1
                """,
                (TaskStatus.QUEUED.value,),
            ).fetchone()
            if row is None:
                return None
            task_id = str(row["task_id"])
            now = datetime.now(UTC).isoformat()
            cursor = conn.execute(
                """
                UPDATE background_tasks
                SET status = ?, updated_at = ?, error = NULL
                WHERE task_id = ? AND status = ?
                """,
                (
                    TaskStatus.RUNNING.value,
                    now,
                    task_id,
                    TaskStatus.QUEUED.value,
                ),
            )
            if cursor.rowcount != 1:
                return None
            claimed = conn.execute(
                "SELECT * FROM background_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return _task_from_row(claimed) if claimed is not None else None

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
        return _task_from_row(row) if row is not None else None

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

    def recover_interrupted_tasks(self) -> int:
        with self.database.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE background_tasks
                SET status = ?, updated_at = ?, error = ?
                WHERE status = ?
                """,
                (
                    TaskStatus.FAILED.value,
                    datetime.now(UTC).isoformat(),
                    "Process restarted after the task began executing",
                    TaskStatus.RUNNING.value,
                ),
            )
            conn.commit()
            return cursor.rowcount


def _task_from_row(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        task_id=str(row["task_id"]),
        kind=str(row["kind"]),
        status=TaskStatus(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        payload_json=row["payload_json"],
        result_json=row["result_json"],
        error=row["error"],
    )


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


def _source_artifact_from_row(row: sqlite3.Row) -> SourceArtifact:
    metadata = json.loads(row["metadata_json"])
    if not isinstance(metadata, dict):
        raise ValueError("Source artifact metadata must be a JSON object")
    return SourceArtifact(
        artifact_id=str(row["artifact_id"]),
        artifact_type=SourceArtifactType(row["artifact_type"]),
        storage_path=str(row["storage_path"]),
        file_size_bytes=int(row["file_size_bytes"]),
        content_sha256=str(row["content_sha256"]),
        authorization_purpose=str(row["authorization_purpose"]),
        authorized_target=str(row["authorized_target"]),
        sensitivity_level=SensitivityLevel(row["sensitivity_level"]),
        captured_at=str(row["captured_at"]),
        metadata=metadata,
    )
