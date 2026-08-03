import hashlib
import threading
import time
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet

from reborn_core.application import InterviewMode
from reborn_core.core.exceptions import ConfigurationError
from reborn_core.domains import LegacyActivationMode
from reborn_core.infrastructure.backup import BackupService
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteBackupRecordRepository,
    SQLiteDatabase,
    SQLiteTaskRepository,
)
from reborn_core.runtime import BackgroundTaskRunner, TaskRecord, TaskStatus
from reborn_core.security import LegacyActivationPolicy, LocalOwnerAccessPolicy


def migrated_database(settings):
    database = SQLiteDatabase(app_settings=settings)
    MigrationRunner(database).migrate()
    return database


def started_runner(repository, handlers, max_workers=1):
    runner = BackgroundTaskRunner(
        repository,
        handlers=handlers,
        max_workers=max_workers,
        poll_interval_seconds=0.01,
    )
    runner.start()
    return runner


def test_background_task_status_is_persisted(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    runner = started_runner(repository, {"sum": lambda: 2 + 3})
    task_id = runner.submit("sum")

    assert runner.result(task_id) == 5
    task = repository.get_task(task_id)
    assert task is not None
    assert task.status is TaskStatus.SUCCEEDED
    assert task.payload_json is not None
    runner.shutdown()


def test_background_task_result_survives_future_pruning(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    runner = started_runner(repository, {"payload": lambda: {"value": 5}})
    task_id = runner.submit("payload")

    assert runner.result(task_id) == {"value": 5}
    for _ in range(50):
        if task_id not in runner._futures:
            break
        time.sleep(0.01)

    assert task_id not in runner._futures
    assert runner.result(task_id) == {"value": 5}
    runner.shutdown()


def test_background_task_failure_is_persisted(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))

    def fail():
        raise ValueError("boom")

    runner = started_runner(repository, {"failure": fail})
    task_id = runner.submit("failure")

    with pytest.raises(RuntimeError, match="Task failed: boom"):
        runner.result(task_id)
    task = repository.get_task(task_id)
    assert task is not None
    assert task.status is TaskStatus.FAILED
    runner.shutdown()


def test_background_task_runner_prevents_duplicates(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))

    def slow_task():
        time.sleep(0.2)
        return "done"

    runner = started_runner(
        repository,
        {"slow": slow_task, "fast": lambda: "ok"},
    )
    task_id1 = runner.submit("slow")

    with pytest.raises(ValueError, match="A background task of kind 'slow' is already running"):
        runner.submit("slow")

    task_id2 = runner.submit("fast")
    assert runner.result(task_id2) == "ok"
    assert runner.result(task_id1) == "done"
    runner.shutdown()


def test_new_runner_replays_historical_queued_task(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    producer = BackgroundTaskRunner(repository, handlers={"historical": lambda value: value * 2})
    task_id = producer.submit("historical", 21)

    queued = repository.get_task(task_id)
    assert queued is not None
    assert queued.status is TaskStatus.QUEUED

    worker = started_runner(repository, {"historical": lambda value: value * 2})
    assert worker.result(task_id) == 42
    worker.shutdown()


def test_two_runners_claim_a_queued_task_once(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    executions = 0
    lock = threading.Lock()

    def execute_once():
        nonlocal executions
        with lock:
            executions += 1
        return "done"

    producer = BackgroundTaskRunner(repository)
    task_id = producer.submit("once")
    first = started_runner(repository, {"once": execute_once})
    second = started_runner(repository, {"once": execute_once})

    assert first.result(task_id) == "done"
    first.shutdown()
    second.shutdown()
    assert executions == 1


def test_task_payload_round_trips_bytes_paths_and_enums(test_settings, tmp_path):
    repository = SQLiteTaskRepository(migrated_database(test_settings))

    def inspect_payload(audio, path, mode):
        return {
            "audio": audio.decode("utf-8"),
            "path": str(path),
            "mode": mode,
        }

    runner = started_runner(repository, {"inspect": inspect_payload})
    task_id = runner.submit(
        "inspect",
        "语音".encode(),
        tmp_path / "voice.wav",
        InterviewMode.LIFE_STORY,
    )

    assert runner.result(task_id) == {
        "audio": "语音",
        "path": str(tmp_path / "voice.wav"),
        "mode": InterviewMode.LIFE_STORY.value,
    }
    runner.shutdown()


def test_missing_payload_and_unknown_kind_fail_cleanly(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    now = datetime.now(UTC).isoformat()
    repository.enqueue_task(
        TaskRecord(
            task_id="legacy",
            kind="legacy",
            status=TaskStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
    )
    runner = started_runner(repository, {"legacy": lambda: None})

    with pytest.raises(RuntimeError, match="payload is missing"):
        runner.result("legacy")
    unknown_id = runner.submit("unknown")
    with pytest.raises(RuntimeError, match="No task handler"):
        runner.result(unknown_id)
    runner.shutdown()


def test_encrypted_backup_and_recovery_drill(test_settings):
    key = Fernet.generate_key().decode("ascii")
    settings = test_settings.model_copy(
        update={"backup_encryption_key": key, "backup_require_encryption": True}
    )
    database = migrated_database(settings)
    vault = settings.base_dir / "data" / "memories"
    vault.mkdir(parents=True)
    (vault / "source.md").write_text("source material", encoding="utf-8")
    service = BackupService(
        settings,
        SQLiteBackupRecordRepository(database),
        LocalOwnerAccessPolicy(),
    )

    path = service.create_backup()
    result = service.run_recovery_drill(path)

    assert path.name.endswith(".zip.fernet")
    assert result["verified"] is True
    assert result["encrypted"] is True
    assert result["profile_included"] is True
    assert result["sqlite_integrity"] == "ok"


def test_backup_key_rotation_preserves_source_and_uses_new_key(test_settings):
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")
    old_settings = test_settings.model_copy(
        update={"backup_encryption_key": old_key, "backup_require_encryption": True}
    )
    database = migrated_database(old_settings)
    vault = old_settings.base_dir / "data" / "memories"
    vault.mkdir(parents=True)
    (vault / "journal.md").write_text("family memory", encoding="utf-8")
    repository = SQLiteBackupRecordRepository(database)
    old_service = BackupService(old_settings, repository, LocalOwnerAccessPolicy())
    source = old_service.create_backup()
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()

    new_settings = old_settings.model_copy(
        update={
            "backup_encryption_key": new_key,
            "backup_previous_encryption_key": old_key,
        }
    )
    new_service = BackupService(new_settings, repository, LocalOwnerAccessPolicy())
    rotated = new_service.rotate_encryption_key(source)
    result = new_service.run_recovery_drill(rotated)

    assert source.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_digest
    assert rotated != source
    assert ".rotated-" in rotated.name
    assert result["sqlite_integrity"] == "ok"
    with pytest.raises(ValueError, match="decryption failed"):
        old_service.verify_backup(rotated)


def test_failed_key_rotation_does_not_publish_output(test_settings):
    old_key = Fernet.generate_key().decode("ascii")
    settings = test_settings.model_copy(update={"backup_encryption_key": old_key})
    database = migrated_database(settings)
    repository = SQLiteBackupRecordRepository(database)
    source = BackupService(settings, repository, LocalOwnerAccessPolicy()).create_backup()
    wrong_settings = settings.model_copy(
        update={
            "backup_encryption_key": Fernet.generate_key().decode("ascii"),
            "backup_previous_encryption_key": Fernet.generate_key().decode("ascii"),
        }
    )
    service = BackupService(wrong_settings, repository, LocalOwnerAccessPolicy())
    before = set(source.parent.iterdir())

    with pytest.raises(ValueError, match="decryption failed"):
        service.rotate_encryption_key(source)

    assert set(source.parent.iterdir()) == before


def test_invalid_backup_key_has_actionable_error(test_settings):
    settings = test_settings.model_copy(
        update={"backup_encryption_key": "invalid-key", "backup_require_encryption": True}
    )
    service = BackupService(
        settings,
        SQLiteBackupRecordRepository(migrated_database(settings)),
        LocalOwnerAccessPolicy(),
    )

    with pytest.raises(ConfigurationError, match="完整的 44 个字符"):
        service.create_backup()


def test_legacy_activation_requires_complete_evidence(test_settings):
    path = test_settings.resolved_legacy_activation_file
    path.parent.mkdir(parents=True)
    path.write_text('{"activated": true}', encoding="utf-8")
    settings = test_settings.model_copy(
        update={"legacy_activation_mode": LegacyActivationMode.ACTIVATION_FILE}
    )

    assert LegacyActivationPolicy(settings).evaluate().active is False
