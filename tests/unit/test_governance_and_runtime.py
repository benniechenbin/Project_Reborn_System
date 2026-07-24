import time

import pytest
from cryptography.fernet import Fernet

from reborn_core.core.exceptions import ConfigurationError
from reborn_core.domains import LegacyActivationMode
from reborn_core.infrastructure.backup import BackupService
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteBackupRecordRepository,
    SQLiteDatabase,
    SQLiteTaskRepository,
)
from reborn_core.runtime import BackgroundTaskRunner, TaskStatus
from reborn_core.security import LegacyActivationPolicy, LocalOwnerAccessPolicy


def migrated_database(settings):
    database = SQLiteDatabase(app_settings=settings)
    MigrationRunner(database).migrate()
    return database


def test_background_task_status_is_persisted(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    runner = BackgroundTaskRunner(repository, max_workers=1)
    task_id = runner.submit("sum", lambda: 2 + 3)

    assert runner.result(task_id) == 5
    task = repository.get_task(task_id)
    assert task is not None
    assert task.status is TaskStatus.SUCCEEDED
    runner.shutdown()


def test_background_task_result_survives_future_pruning(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    runner = BackgroundTaskRunner(repository, max_workers=1)
    task_id = runner.submit("payload", lambda: {"value": 5})

    assert runner.result(task_id) == {"value": 5}
    for _ in range(50):
        if task_id not in runner._futures:
            break
        time.sleep(0.01)

    assert task_id not in runner._futures
    assert runner.result(task_id) == {"value": 5}
    runner.shutdown()


def test_background_task_failure_after_pruning_has_clear_error(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    runner = BackgroundTaskRunner(repository, max_workers=1)

    def fail():
        raise ValueError("boom")

    task_id = runner.submit("failure", fail)
    with pytest.raises(ValueError, match="boom"):
        runner.result(task_id)
    for _ in range(50):
        if task_id not in runner._futures:
            break
        time.sleep(0.01)

    assert task_id not in runner._futures
    with pytest.raises(RuntimeError, match="Task failed: boom"):
        runner.result(task_id)
    runner.shutdown()


def test_background_task_runner_prevents_duplicates(test_settings):
    repository = SQLiteTaskRepository(migrated_database(test_settings))
    runner = BackgroundTaskRunner(repository, max_workers=1)

    def slow_task():
        time.sleep(0.5)
        return "done"

    # Start a slow running task
    task_id1 = runner.submit("slow", slow_task)

    # Submitting another task of the same kind should fail immediately
    with pytest.raises(ValueError, match="A background task of kind 'slow' is already running"):
        runner.submit("slow", lambda: "another")

    # Submitting a task of a different kind should succeed
    task_id2 = runner.submit("fast", lambda: "ok")
    assert runner.result(task_id2) == "ok"

    # Wait for the first task to finish
    assert runner.result(task_id1) == "done"
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
