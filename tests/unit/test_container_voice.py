import pytest

from reborn_core.application import InterviewMode
from reborn_core.container import Container


class StubSTTEngine:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.audio_bytes: bytes | None = None

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        self.audio_bytes = audio_bytes
        return self.transcript


class StubInterviewService:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, str]], InterviewMode]] = []

    def process_interview(
        self,
        chat_history: list[dict[str, str]],
        mode: InterviewMode,
    ) -> dict[str, str]:
        self.calls.append((chat_history, mode))
        return {"identity_snapshot_id": "snapshot-1"}


def test_process_voice_capture_rejects_empty_transcript(test_settings):
    container = Container(app_settings=test_settings)
    container.stt_engine = StubSTTEngine("")

    with pytest.raises(ValueError, match="没有识别到有效语音"):
        container.process_voice_capture(b"audio")


def test_process_voice_capture_runs_interview_for_transcript(test_settings):
    container = Container(app_settings=test_settings)
    stt_engine = StubSTTEngine("今天想记录一段故事。")
    interview_service = StubInterviewService()
    container.stt_engine = stt_engine
    container.interview_service = interview_service

    result = container.process_voice_capture(b"audio")

    assert stt_engine.audio_bytes == b"audio"
    assert result == {
        "transcript": "今天想记录一段故事。",
        "interview": {"identity_snapshot_id": "snapshot-1"},
    }
    assert interview_service.calls == [
        (
            [{"role": "user", "content": "Voice journal:\n今天想记录一段故事。"}],
            InterviewMode.LIFE_STORY,
        )
    ]
