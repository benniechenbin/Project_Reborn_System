import hashlib
import io
import uuid
import wave
from datetime import UTC, datetime

from reborn_core.application.models import (
    SensitivityLevel,
    SourceArtifact,
    SourceArtifactType,
    VoiceArchiveResult,
)
from reborn_core.application.ports import AudioArchiveStoragePort, SourceArtifactRepository
from reborn_core.observability import logger

VOICE_MODEL_TRAINING_PURPOSE = "voice_model_training"


class VoiceArchiveService:
    """Archive explicitly authorized voice-model training recordings."""

    def __init__(
        self,
        storage: AudioArchiveStoragePort,
        repository: SourceArtifactRepository,
    ) -> None:
        self.storage = storage
        self.repository = repository

    def archive(
        self,
        audio_bytes: bytes,
        *,
        script_id: str,
        script_text: str,
        authorized_target: str,
        consent_given: bool,
    ) -> VoiceArchiveResult:
        """Persist one WAV recording and its immutable authorization metadata."""
        if not audio_bytes:
            raise ValueError("Audio bytes must not be empty")
        if not consent_given:
            raise ValueError("必须明确授权后才能归档声音素材")
        target = authorized_target.strip()
        if not target:
            raise ValueError("必须填写授权使用的目标音色模型")
        if not _is_wav(audio_bytes):
            raise ValueError("声音素材必须是有效的 WAV 文件")

        wav_metadata = _wav_metadata(audio_bytes)
        normalized_script_id = script_id.strip()
        normalized_script_text = script_text.strip()
        if not normalized_script_id or not normalized_script_text:
            raise ValueError("朗读脚本标识和内容不能为空")

        artifact_id = uuid.uuid4().hex
        content_sha256 = hashlib.sha256(audio_bytes).hexdigest()
        storage_path = self.storage.save_audio(artifact_id, audio_bytes)
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            artifact_type=SourceArtifactType.AUDIO_DATASET,
            storage_path=storage_path,
            file_size_bytes=len(audio_bytes),
            content_sha256=content_sha256,
            authorization_purpose=VOICE_MODEL_TRAINING_PURPOSE,
            authorized_target=target,
            sensitivity_level=SensitivityLevel.HIGH,
            captured_at=datetime.now(UTC).isoformat(),
            metadata={
                "script_id": normalized_script_id,
                "script_text": normalized_script_text,
                "script_sha256": hashlib.sha256(normalized_script_text.encode("utf-8")).hexdigest(),
                "media_type": "audio/wav",
                **wav_metadata,
            },
        )
        try:
            self.repository.create_source_artifact(artifact)
        except Exception:
            try:
                self.storage.delete_audio(storage_path)
            except Exception as cleanup_exc:
                logger.warning(
                    "Could not remove voice archive file {} for artifact {} after repository failure: {}",
                    storage_path,
                    artifact_id,
                    cleanup_exc,
                )
            raise
        return VoiceArchiveResult(
            artifact_id=artifact.artifact_id,
            storage_path=artifact.storage_path,
            content_sha256=artifact.content_sha256,
            authorized_target=artifact.authorized_target,
        )


def _is_wav(audio_bytes: bytes) -> bool:
    return len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"


def _wav_metadata(audio_bytes: bytes) -> dict[str, int]:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            if wav_file.getcomptype() != "NONE":
                raise ValueError("Voice archive WAV must use uncompressed PCM audio")
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            frames = wav_file.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise ValueError("Voice archive must contain a structurally valid WAV file") from exc

    if channels < 1 or sample_width < 1 or sample_rate < 1:
        raise ValueError("Voice archive WAV has invalid audio parameters")
    if frame_count < 1:
        raise ValueError("Voice archive WAV must contain at least one audio frame")
    expected_frame_bytes = frame_count * channels * sample_width
    if len(frames) != expected_frame_bytes:
        raise ValueError("Voice archive WAV audio data is truncated")

    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "frame_count": frame_count,
    }
