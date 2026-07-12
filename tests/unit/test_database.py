import sqlite3
from datetime import UTC, datetime

import pytest

from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    PromptMetadata,
)
from reborn_core.container import Container
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteAuditRepository,
    SQLiteBackupRecordRepository,
    SQLiteDatabase,
    SQLiteIdentitySnapshotRepository,
    SQLiteSyncHistoryRepository,
    SQLiteTaskRepository,
)
from reborn_core.infrastructure.database import migrations as migration_module
from reborn_core.runtime import TaskRecord, TaskStatus


@pytest.fixture
def database(tmp_path):
    database = SQLiteDatabase(db_path=tmp_path / "test.db")
    MigrationRunner(database).migrate()
    return database


def test_migrations_create_current_schema(database):
    with database.get_connection() as conn:
        tables = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        versions = [
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

    assert {
        "sync_history",
        "identity_snapshots",
        "background_tasks",
        "backup_records",
        "audit_events",
    } <= tables
    assert versions == [1, 2, 3, 4]
    assert integrity == "ok"


def test_migrations_are_idempotent(database):
    MigrationRunner(database).migrate()

    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]

    assert count == MigrationRunner.LATEST_VERSION


def test_migration_failure_rolls_back_all_changes(tmp_path, monkeypatch):
    database = SQLiteDatabase(db_path=tmp_path / "failed.db")

    def failing_migration(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE should_be_rolled_back (id INTEGER PRIMARY KEY)")
        raise RuntimeError("migration failed")

    monkeypatch.setattr(
        migration_module,
        "_migration_004_backup_and_audit",
        failing_migration,
    )

    with pytest.raises(RuntimeError, match="migration failed"):
        MigrationRunner(database).migrate()

    with database.get_connection() as conn:
        tables = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    assert "should_be_rolled_back" not in tables
    assert "schema_migrations" not in tables


def test_migrations_upgrade_partial_database_without_losing_data(tmp_path):
    db_path = tmp_path / "partial.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00');
            CREATE TABLE sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time TEXT NOT NULL,
                audio_duration REAL NOT NULL DEFAULT 0,
                notes_count INTEGER NOT NULL DEFAULT 0,
                word_count INTEGER NOT NULL DEFAULT 0,
                generation_id TEXT
            );
            INSERT INTO sync_history
                (sync_time, audio_duration, notes_count, word_count, generation_id)
            VALUES ('2026-01-01', 1.5, 2, 30, 'generation-1');
            """
        )
        conn.commit()
    finally:
        conn.close()

    database = SQLiteDatabase(db_path=db_path)
    MigrationRunner(database).migrate()

    with database.get_connection() as upgraded:
        record = upgraded.execute("SELECT * FROM sync_history").fetchone()
        versions = [
            row["version"]
            for row in upgraded.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]

    assert record["generation_id"] == "generation-1"
    assert record["word_count"] == 30
    assert versions == [1, 2, 3, 4]


def test_database_transaction_commit_and_rollback(database):
    with database.transaction() as conn:
        conn.execute("INSERT INTO sync_history (sync_time) VALUES (?)", ("2026-01-01",))

    with pytest.raises(ValueError, match="rollback"):
        with database.transaction() as conn:
            conn.execute("INSERT INTO sync_history (sync_time) VALUES (?)", ("2026-01-02",))
            raise ValueError("rollback")

    with database.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sync_history").fetchone()[0]

    assert count == 1


def test_sync_history_repository_returns_ordered_entries(database):
    repository = SQLiteSyncHistoryRepository(database)
    repository.save_sync_record(
        {
            "sync_time": "2026-01-02T00:00:00+00:00",
            "audio_duration": 2.5,
            "notes_count": 2,
            "word_count": 20,
            "generation_id": "gen_2",
        }
    )
    repository.save_sync_record(
        {
            "sync_time": "2026-01-01T00:00:00+00:00",
            "audio_duration": 1.5,
            "notes_count": 1,
            "word_count": 10,
            "generation_id": "gen_1",
        }
    )

    history = repository.list_sync_history()

    assert [entry.generation_id for entry in history] == ["gen_1", "gen_2"]
    assert history[0].audio_duration == 1.5


def test_identity_snapshot_repository_lifecycle(database):
    repository = SQLiteIdentitySnapshotRepository(database)
    snapshot = IdentitySnapshot(
        snapshot_id="snap_1",
        parent_snapshot_id=None,
        content="I am a test identity",
        content_sha256="sha123",
        source_ids=("doc1", "doc2"),
        model=ModelMetadata(provider="openai", model_name="gpt-4"),
        prompt=PromptMetadata(prompt_id="p1", version="1.0", sha256="psha"),
        generation_params={"temp": 0.7},
        status=IdentitySnapshotStatus.PENDING_REVIEW,
        created_at=datetime.now(UTC).isoformat(),
        active=False,
    )

    repository.create_identity_snapshot(snapshot)
    retrieved = repository.get_identity_snapshot("snap_1")
    reviewed = repository.review_identity_snapshot(
        "snap_1", IdentitySnapshotStatus.APPROVED, "admin", "Looks good"
    )
    active = repository.get_active_identity_snapshot()

    assert retrieved is not None
    assert retrieved.status is IdentitySnapshotStatus.PENDING_REVIEW
    assert reviewed.status is IdentitySnapshotStatus.APPROVED
    assert reviewed.active is True
    assert active is not None
    assert active.snapshot_id == "snap_1"


def test_task_repository_marks_unfinished_tasks_failed(database):
    repository = SQLiteTaskRepository(database)
    now = datetime.now(UTC).isoformat()
    repository.create_task(
        TaskRecord(
            task_id="task_1",
            kind="sync",
            status=TaskStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
    )

    repository.update_task("task_1", TaskStatus.RUNNING)
    assert repository.has_active_task_of_kind("sync")
    assert repository.mark_unfinished_tasks_failed() == 1
    retrieved = repository.get_task("task_1")

    assert retrieved is not None
    assert retrieved.status is TaskStatus.FAILED


def test_backup_and_audit_repositories_are_isolated(database):
    audit_repository = SQLiteAuditRepository(database)
    backup_repository = SQLiteBackupRecordRepository(database)

    audit_repository.append_audit_event("login", "system", "user_1", "success", {"ip": "127.0.0.1"})
    backup_repository.save_backup_record("back_1", "/path/to/back", "sha", True, "success")

    with database.get_connection() as conn:
        audit = conn.execute("SELECT * FROM audit_events").fetchone()
        backup = conn.execute("SELECT * FROM backup_records").fetchone()

    assert audit["action"] == "login"
    assert "127.0.0.1" in audit["details_json"]
    assert backup["backup_id"] == "back_1"


def test_container_exposes_independent_repositories(test_settings):
    container = Container(test_settings)

    assert container.identity_snapshot_repository.database is container.database
    assert container.task_repository.database is container.database
    assert container.sync_history_repository.database is container.database
    assert container.backup_record_repository.database is container.database
    assert container.audit_repository.database is container.database
    assert not hasattr(container, "db_manager")
