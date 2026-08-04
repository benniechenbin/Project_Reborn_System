import hashlib
import io
import wave

import pytest

from reborn_core.application import SensitivityLevel, SourceArtifactType, VoiceArchiveService
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteDatabase,
    SQLiteSourceArtifactRepository,
)
from reborn_core.infrastructure.memory import LocalAudioArchiveStorage


def wav_bytes(
    payload: bytes = b"\x00\x01" * 64,
    *,
    sample_rate: int = 48000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    frame_width = channels * sample_width
    padding = (-len(payload)) % frame_width
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(payload + (b"\x00" * padding))
    return output.getvalue()


def build_service(test_settings):
    database = SQLiteDatabase(app_settings=test_settings)
    MigrationRunner(database).migrate()
    repository = SQLiteSourceArtifactRepository(database)
    storage = LocalAudioArchiveStorage(test_settings.base_dir / "data" / "audio")
    return VoiceArchiveService(storage, repository), repository, storage


def test_voice_archive_persists_file_and_compliance_metadata(test_settings):
    service, repository, storage = build_service(test_settings)
    audio = wav_bytes("家庭声音".encode())

    result = service.archive(
        audio,
        script_id="comforting_companionship",
        script_text="请慢慢呼吸，我会陪着你。",
        authorized_target="family-voice-v1",
        consent_given=True,
    )

    artifact = repository.get_source_artifact(result.artifact_id)
    saved_path = storage.audio_root / result.storage_path
    assert saved_path.read_bytes() == audio
    assert artifact is not None
    assert artifact.artifact_type is SourceArtifactType.AUDIO_DATASET
    assert artifact.content_sha256 == hashlib.sha256(audio).hexdigest()
    assert artifact.file_size_bytes == len(audio)
    assert artifact.authorization_purpose == "voice_model_training"
    assert artifact.authorized_target == "family-voice-v1"
    assert artifact.sensitivity_level is SensitivityLevel.HIGH
    assert artifact.metadata["script_id"] == "comforting_companionship"
    assert artifact.metadata["script_text"] == "请慢慢呼吸，我会陪着你。"
    assert artifact.metadata["sample_rate_hz"] == 48000
    assert artifact.metadata["channels"] == 1
    assert artifact.metadata["sample_width_bits"] == 16
    assert artifact.metadata["frame_count"] > 0


@pytest.mark.parametrize(
    ("audio", "target", "consent", "message"),
    [
        (wav_bytes(), "family-voice-v1", False, "明确授权"),
        (wav_bytes(), "   ", True, "目标音色模型"),
        (b"", "family-voice-v1", True, "empty"),
        (b"not-wav", "family-voice-v1", True, "WAV"),
        (b"RIFF\x04\x00\x00\x00WAVE", "family-voice-v1", True, "WAV"),
        (wav_bytes()[:-8], "family-voice-v1", True, "WAV"),
        (wav_bytes(b""), "family-voice-v1", True, "WAV"),
    ],
)
def test_voice_archive_rejects_noncompliant_input(
    test_settings,
    audio,
    target,
    consent,
    message,
):
    service, repository, _storage = build_service(test_settings)

    with pytest.raises(ValueError, match=message):
        service.archive(
            audio,
            script_id="neutral",
            script_text="测试脚本",
            authorized_target=target,
            consent_given=consent,
        )

    assert repository.list_source_artifacts() == []


def test_voice_archive_removes_new_file_when_repository_write_fails(test_settings):
    class FailingRepository:
        def create_source_artifact(self, artifact):
            raise RuntimeError("database unavailable")

        def get_source_artifact(self, artifact_id):
            return None

        def list_source_artifacts(self, artifact_type=None, limit=20):
            return []

    storage = LocalAudioArchiveStorage(test_settings.base_dir / "data" / "audio")
    service = VoiceArchiveService(storage, FailingRepository())

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.archive(
            wav_bytes(),
            script_id="neutral",
            script_text="测试脚本",
            authorized_target="family-voice-v1",
            consent_given=True,
        )

    assert not storage.dataset_root.exists() or list(storage.dataset_root.iterdir()) == []


def test_voice_archive_preserves_database_error_when_cleanup_fails(test_settings, monkeypatch):
    class FailingRepository:
        def create_source_artifact(self, artifact):
            raise RuntimeError("database unavailable")

        def get_source_artifact(self, artifact_id):
            return None

        def list_source_artifacts(self, artifact_type=None, limit=20):
            return []

    class CleanupFailingStorage(LocalAudioArchiveStorage):
        def delete_audio(self, storage_path: str) -> None:
            raise PermissionError("archive file is locked")

    warnings = []

    class RecordingLogger:
        def warning(self, message, *args):
            warnings.append((message, args))

    from reborn_core.application.services import voice_archive as voice_archive_module

    monkeypatch.setattr(voice_archive_module, "logger", RecordingLogger())
    storage = CleanupFailingStorage(test_settings.base_dir / "data" / "audio")
    service = VoiceArchiveService(storage, FailingRepository())

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.archive(
            wav_bytes(),
            script_id="neutral",
            script_text="test script",
            authorized_target="family-voice-v1",
            consent_given=True,
        )

    assert warnings
