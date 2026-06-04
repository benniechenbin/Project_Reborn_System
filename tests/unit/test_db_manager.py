import pytest
from datetime import datetime, UTC
from reborn_core.domains.memory.relational.db_manager import DBManager
from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    PromptMetadata,
)
from reborn_core.runtime import TaskRecord, TaskStatus


@pytest.fixture
def db_manager(tmp_path):
    db_path = tmp_path / "test.db"
    return DBManager(db_path=db_path)


def test_db_migration(db_manager):
    # Check if tables exist
    with db_manager.get_connection() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t["name"] for t in tables]
        assert "sync_history" in table_names
        assert "identity_snapshots" in table_names
        assert "background_tasks" in table_names
        assert "backup_records" in table_names
        assert "audit_events" in table_names


def test_db_transaction_commit(db_manager):
    with db_manager.transaction() as conn:
        conn.execute("INSERT INTO sync_history (sync_time) VALUES (?)", ("2026-01-01",))

    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT count(*) as count FROM sync_history").fetchone()
        assert row["count"] == 1


def test_db_transaction_rollback(db_manager):
    with pytest.raises(ValueError):
        with db_manager.transaction() as conn:
            conn.execute("INSERT INTO sync_history (sync_time) VALUES (?)", ("2026-01-01",))
            raise ValueError("Rollback trigger")

    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT count(*) as count FROM sync_history").fetchone()
        assert row["count"] == 0


def test_save_sync_record(db_manager):
    metrics = {
        "audio_duration": 10.5,
        "notes_count": 5,
        "word_count": 1000,
        "generation_id": "gen_123",
    }
    db_manager.save_sync_record(metrics)

    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT * FROM sync_history").fetchone()
        assert row["audio_duration"] == 10.5
        assert row["notes_count"] == 5
        assert row["word_count"] == 1000
        assert row["generation_id"] == "gen_123"


def test_identity_snapshot_lifecycle(db_manager):
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

    db_manager.create_identity_snapshot(snapshot)

    retrieved = db_manager.get_identity_snapshot("snap_1")
    assert retrieved.snapshot_id == "snap_1"
    assert retrieved.status == IdentitySnapshotStatus.PENDING_REVIEW

    # Review and approve
    reviewed = db_manager.review_identity_snapshot(
        "snap_1", IdentitySnapshotStatus.APPROVED, "admin", "Looks good"
    )
    assert reviewed.status == IdentitySnapshotStatus.APPROVED
    assert reviewed.active is True

    # Check if it's the active one
    active = db_manager.get_active_identity_snapshot()
    assert active.snapshot_id == "snap_1"


def test_task_management(db_manager):
    task = TaskRecord(
        task_id="task_1",
        kind="sync",
        status=TaskStatus.QUEUED,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )
    db_manager.create_task(task)

    db_manager.update_task("task_1", TaskStatus.RUNNING)
    retrieved = db_manager.get_task("task_1")
    assert retrieved.status == TaskStatus.RUNNING

    # Fail unfinished tasks
    db_manager.mark_unfinished_tasks_failed()
    retrieved = db_manager.get_task("task_1")
    assert retrieved.status == TaskStatus.FAILED


def test_audit_and_backup(db_manager):
    db_manager.append_audit_event("login", "system", "user_1", "success", {"ip": "127.0.0.1"})
    db_manager.save_backup_record("back_1", "/path/to/back", "sha", True, "success")

    with db_manager.get_connection() as conn:
        audit = conn.execute("SELECT * FROM audit_events").fetchone()
        assert audit["action"] == "login"
        assert "127.0.0.1" in audit["details_json"]

        backup = conn.execute("SELECT * FROM backup_records").fetchone()
        assert backup["backup_id"] == "back_1"
