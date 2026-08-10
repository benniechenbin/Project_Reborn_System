import os
import uuid
from pathlib import Path


class LocalReflectionSourceStorage:
    """Atomically stores nightly-reflection transcripts below the memory vault."""

    def __init__(self, obsidian_root: Path, source_artifacts_folder: str) -> None:
        self.obsidian_root = obsidian_root.resolve()
        self.archive_root = (
            self.obsidian_root / source_artifacts_folder / "NightlyReflections"
        ).resolve()

    def save(self, artifact_id: str, payload: bytes) -> str:
        if not payload:
            raise ValueError("Reflection source payload must not be empty")
        self.archive_root.mkdir(parents=True, exist_ok=True)
        target = self.archive_root / f"{artifact_id}.json"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target.relative_to(self.obsidian_root).as_posix()

    def read(self, storage_path: str) -> bytes:
        target = self._resolve(storage_path)
        if not target.is_file():
            raise FileNotFoundError(f"Reflection source file not found: {storage_path}")
        return target.read_bytes()

    def delete(self, storage_path: str) -> None:
        self._resolve(storage_path).unlink(missing_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        target = (self.obsidian_root / storage_path).resolve()
        if not target.is_relative_to(self.archive_root):
            raise ValueError("Reflection source path escaped the configured archive root")
        return target
