import hashlib
import io
import json
import os
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from reborn_core.config import Settings
from reborn_core.security import AccessAction, AccessContext
from reborn_core.security.access import AccessPolicy


class BackupRecordRepository(Protocol):
    def save_backup_record(
        self,
        backup_id: str,
        path: str,
        sha256: str,
        encrypted: bool,
        status: str,
        detail: str | None = None,
    ) -> None: ...


class BackupService:
    """创建可移植的加密备份，并执行非破坏性恢复演练。"""

    def __init__(
        self,
        settings: Settings,
        repository: BackupRecordRepository,
        access_policy: AccessPolicy,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.access_policy = access_policy

    def create_backup(self, context: AccessContext | None = None) -> Path:
        context = context or AccessContext()
        self.access_policy.require(AccessAction.BACKUP, "digital-estate", context)
        backup_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        key = self._encryption_key()
        self.settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="reborn-backup-") as temp:
            db_snapshot = Path(temp) / "reborn.db"
            self._snapshot_sqlite(db_snapshot)
            archive_bytes = self._build_archive(backup_id, db_snapshot)

        encrypted = key is not None
        final_bytes = Fernet(key).encrypt(archive_bytes) if key else archive_bytes
        suffix = ".zip.fernet" if encrypted else ".zip"
        destination = self.settings.resolved_backup_dir / f"reborn_{backup_id}{suffix}"
        temp_destination = destination.with_name(f".{destination.name}.tmp")
        try:
            temp_destination.write_bytes(final_bytes)
            os.replace(temp_destination, destination)
        finally:
            if temp_destination.exists():
                temp_destination.unlink()

        digest = _sha256_bytes(final_bytes)
        self.repository.save_backup_record(
            backup_id, str(destination), digest, encrypted, "created"
        )
        return destination

    def verify_backup(self, path: Path, context: AccessContext | None = None) -> dict[str, object]:
        context = context or AccessContext()
        self.access_policy.require(AccessAction.RESTORE, str(path), context)
        payload = self._read_archive(path)
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            for item in manifest["files"]:
                content = archive.read(item["archive_path"])
                if _sha256_bytes(content) != item["sha256"]:
                    raise ValueError(f"Backup checksum mismatch: {item['archive_path']}")
        return {
            "backup_id": manifest["backup_id"],
            "verified": True,
            "file_count": len(manifest["files"]),
            "encrypted": path.name.endswith(".fernet"),
        }

    def run_recovery_drill(
        self,
        path: Path,
        context: AccessContext | None = None,
    ) -> dict[str, object]:
        result = self.verify_backup(path, context)
        with tempfile.TemporaryDirectory(prefix="reborn-recovery-drill-") as temp:
            drill_root = Path(temp)
            with zipfile.ZipFile(io.BytesIO(self._read_archive(path)), "r") as archive:
                for member in archive.infolist():
                    destination = (drill_root / member.filename).resolve()
                    if drill_root.resolve() not in destination.parents:
                        raise ValueError(f"Unsafe backup member path: {member.filename}")
                    archive.extract(member, drill_root)
            restored_db = drill_root / "sqlite" / "reborn.db"
            conn = sqlite3.connect(restored_db)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                conn.close()
            if integrity != "ok":
                raise ValueError(f"Restored SQLite integrity check failed: {integrity}")
            result["sqlite_integrity"] = integrity

        self.repository.save_backup_record(
            f"drill_{uuid.uuid4().hex[:12]}",
            str(path),
            _sha256_bytes(path.read_bytes()),
            bool(result["encrypted"]),
            "recovery_drill_passed",
            detail=json.dumps(result, ensure_ascii=False),
        )
        return result

    def _read_archive(self, path: Path) -> bytes:
        payload = path.read_bytes()
        if not path.name.endswith(".fernet"):
            return payload
        key = self._encryption_key(required=True)
        assert key is not None
        try:
            return Fernet(key).decrypt(payload)
        except InvalidToken as exc:
            raise ValueError("Backup decryption failed") from exc

    def _build_archive(self, backup_id: str, db_snapshot: Path) -> bytes:
        files: list[tuple[Path, str]] = [(db_snapshot, "sqlite/reborn.db")]
        vault = self.settings.active_obsidian_path or self.settings.base_dir / "data" / "memories"
        if vault.exists():
            files.extend(
                (path, f"vault/{path.relative_to(vault).as_posix()}")
                for path in vault.rglob("*")
                if path.is_file()
            )
        activation = self.settings.resolved_legacy_activation_file
        if activation.exists():
            files.append((activation, "governance/legacy_activation.json"))

        manifest_files = []
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source, archive_path in files:
                content = source.read_bytes()
                archive.writestr(archive_path, content)
                manifest_files.append(
                    {
                        "archive_path": archive_path,
                        "sha256": _sha256_bytes(content),
                        "size": len(content),
                    }
                )
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "backup_id": backup_id,
                        "created_at": datetime.now(UTC).isoformat(),
                        "files": manifest_files,
                        "rebuildable_data_excluded": ["retrieval index", "local models"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        return output.getvalue()

    def _snapshot_sqlite(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(self.settings.resolved_db_path)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

    def _encryption_key(self, required: bool = False) -> bytes | None:
        secret = self.settings.backup_encryption_key
        if secret is None:
            if required or self.settings.backup_require_encryption:
                raise ValueError(
                    "BACKUP_ENCRYPTION_KEY is required. Generate a Fernet key and store it "
                    "outside the project before creating backups."
                )
            return None
        value = secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
        return value.encode("ascii")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
