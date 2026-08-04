import os
import uuid
from pathlib import Path


class LocalAudioArchiveStorage:
    """Atomically persists voice dataset WAV files below a configured audio root."""

    def __init__(self, audio_root: Path) -> None:
        self.audio_root = audio_root.resolve()
        self.dataset_root = self.audio_root / "voice_dataset"

    def save_audio(self, artifact_id: str, audio_bytes: bytes) -> str:
        self.dataset_root.mkdir(parents=True, exist_ok=True)
        target = self.dataset_root / f"{artifact_id}.wav"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(audio_bytes)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target.relative_to(self.audio_root).as_posix()

    def delete_audio(self, storage_path: str) -> None:
        target = (self.audio_root / storage_path).resolve()
        if not target.is_relative_to(self.audio_root):
            raise ValueError("Audio archive path escaped the configured audio root")
        target.unlink(missing_ok=True)
