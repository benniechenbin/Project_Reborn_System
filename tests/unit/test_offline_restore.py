import hashlib
import json
import sqlite3
import zipfile

import pytest
from cryptography.fernet import Fernet

from reborn_core.infrastructure.backup import BackupService
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteBackupRecordRepository,
    SQLiteDatabase,
)
from reborn_core.security import LocalOwnerAccessPolicy
from scripts.offline_restore import restore_backup


def create_service(settings):
    database = SQLiteDatabase(app_settings=settings)
    MigrationRunner(database).migrate()
    return BackupService(
        settings,
        SQLiteBackupRecordRepository(database),
        LocalOwnerAccessPolicy(),
    )


def test_standalone_offline_restore_recovers_portable_assets(test_settings, tmp_path):
    key = Fernet.generate_key().decode("ascii")
    settings = test_settings.model_copy(update={"backup_encryption_key": key})
    vault = settings.base_dir / "data" / "memories"
    vault.mkdir(parents=True)
    (vault / "journal.md").write_text("important memory", encoding="utf-8")
    backup = create_service(settings).create_backup()
    output = tmp_path / "restored"

    result = restore_backup(backup, output, key)

    assert result["sqlite_integrity"] == "ok"
    assert (output / "profile" / "project_profile.toml").is_file()
    assert (output / "vault" / "journal.md").read_text(encoding="utf-8") == "important memory"
    assert (output / "sqlite" / "reborn.db").is_file()


def test_standalone_offline_restore_rejects_path_traversal(tmp_path):
    key = Fernet.generate_key()
    database = tmp_path / "source.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE family (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    database_bytes = database.read_bytes()
    archive_zip = tmp_path / "unsafe.zip"
    manifest = {
        "backup_id": "unsafe",
        "files": [
            {
                "archive_path": "sqlite/reborn.db",
                "sha256": hashlib.sha256(database_bytes).hexdigest(),
                "size": len(database_bytes),
            }
        ],
    }
    with zipfile.ZipFile(archive_zip, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("sqlite/reborn.db", database_bytes)
        archive.writestr("../escape.txt", "escape")
    encrypted = tmp_path / "unsafe.zip.fernet"
    encrypted.write_bytes(Fernet(key).encrypt(archive_zip.read_bytes()))

    with pytest.raises(ValueError, match="不安全|越界"):
        restore_backup(encrypted, tmp_path / "output", key.decode("ascii"))

    assert not (tmp_path / "escape.txt").exists()


def test_standalone_offline_restore_rejects_checksum_mismatch(tmp_path):
    key = Fernet.generate_key()
    archive_zip = tmp_path / "corrupt.zip"
    manifest = {
        "backup_id": "corrupt",
        "files": [
            {
                "archive_path": "sqlite/reborn.db",
                "sha256": "0" * 64,
                "size": 3,
            }
        ],
    }
    with zipfile.ZipFile(archive_zip, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("sqlite/reborn.db", b"bad")
    encrypted = tmp_path / "corrupt.zip.fernet"
    encrypted.write_bytes(Fernet(key).encrypt(archive_zip.read_bytes()))

    with pytest.raises(ValueError, match="哈希校验失败"):
        restore_backup(encrypted, tmp_path / "output", key.decode("ascii"))
