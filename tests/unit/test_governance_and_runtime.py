from cryptography.fernet import Fernet

from reborn_core.config import LegacyActivationMode
from reborn_core.domains.memory.relational import DBManager
from reborn_core.infrastructure.backup import BackupService
from reborn_core.runtime import BackgroundTaskRunner, TaskStatus
from reborn_core.security import LegacyActivationPolicy, LocalOwnerAccessPolicy


def test_background_task_status_is_persisted(test_settings):
    db = DBManager(app_settings=test_settings)
    runner = BackgroundTaskRunner(db, max_workers=1)
    runner.start()
    task_id = runner.submit("sum", lambda: 2 + 3)

    assert runner.result(task_id) == 5
    assert db.get_task(task_id).status is TaskStatus.SUCCEEDED
    runner.shutdown()


def test_encrypted_backup_and_recovery_drill(test_settings):
    key = Fernet.generate_key().decode("ascii")
    settings = test_settings.model_copy(
        update={"backup_encryption_key": key, "backup_require_encryption": True}
    )
    db = DBManager(app_settings=settings)
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


def test_legacy_activation_requires_complete_evidence(test_settings):
    path = test_settings.resolved_legacy_activation_file
    path.parent.mkdir(parents=True)
    path.write_text('{"activated": true}', encoding="utf-8")
    settings = test_settings.model_copy(
        update={"legacy_activation_mode": LegacyActivationMode.ACTIVATION_FILE}
    )

    assert LegacyActivationPolicy(settings).evaluate().active is False
