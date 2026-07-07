import time

from cryptography.fernet import Fernet
import pytest

from reborn_core.config import LegacyActivationMode
from reborn_core.core.exceptions import ConfigurationError
from reborn_core.domains.memory.relational import DBManager
from reborn_core.infrastructure.backup import BackupService
from reborn_core.runtime import BackgroundTaskRunner, TaskStatus
from reborn_core.security import LegacyActivationPolicy, LocalOwnerAccessPolicy


def migrated_db(settings):
    db = DBManager(app_settings=settings)
    db.migrate()
    return db


def test_background_task_status_is_persisted(test_settings):
    db = migrated_db(test_settings)
    runner = BackgroundTaskRunner(db, max_workers=1)
    task_id = runner.submit("sum", lambda: 2 + 3)

    assert runner.result(task_id) == 5
    assert db.get_task(task_id).status is TaskStatus.SUCCEEDED
    runner.shutdown()


def test_background_task_result_survives_future_pruning(test_settings):
    db = migrated_db(test_settings)
    runner = BackgroundTaskRunner(db, max_workers=1)
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
    db = migrated_db(test_settings)
    runner = BackgroundTaskRunner(db, max_workers=1)

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


def test_encrypted_backup_and_recovery_drill(test_settings):
    key = Fernet.generate_key().decode("ascii")
    settings = test_settings.model_copy(
        update={"backup_encryption_key": key, "backup_require_encryption": True}
    )
    db = migrated_db(settings)
    vault = settings.base_dir / "data" / "memories"
    vault.mkdir(parents=True)
    (vault / "source.md").write_text("source material", encoding="utf-8")
    service = BackupService(settings, db, LocalOwnerAccessPolicy())

    path = service.create_backup()
    result = service.run_recovery_drill(path)

    assert path.name.endswith(".zip.fernet")
    assert result["verified"] is True
    assert result["encrypted"] is True
    assert result["sqlite_integrity"] == "ok"


def test_invalid_backup_key_has_actionable_error(test_settings):
    settings = test_settings.model_copy(
        update={"backup_encryption_key": "invalid-key", "backup_require_encryption": True}
    )
    service = BackupService(settings, migrated_db(settings), LocalOwnerAccessPolicy())

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
