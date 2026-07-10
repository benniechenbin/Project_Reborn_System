import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from reborn_core.core.exceptions import ConfigurationError, InfrastructureError
from reborn_core.infrastructure.brain.llm_router import LLMRouter
from reborn_core.infrastructure.brain.stt_engine import STTEngine


@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    # Mock chat.completions.create response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    client.chat.completions.create.return_value = mock_response
    return client


def test_llm_router_initialization(test_settings):
    # Test valid init
    router = LLMRouter(app_settings=test_settings, client=MagicMock())
    assert router.model_name == test_settings.llm_model_name
    assert router.model_metadata.model_name == test_settings.llm_model_name


def test_llm_router_missing_api_key(test_settings):
    test_settings.llm_api_key = None
    with pytest.raises(ValueError, match="未在 .env 中找到 LLM_API_KEY"):
        LLMRouter(app_settings=test_settings)


def test_llm_router_generate_response(test_settings, mock_openai_client):
    router = LLMRouter(app_settings=test_settings, client=mock_openai_client)
    msgs = [{"role": "user", "content": "hello"}]
    response = router.generate_response(msgs)

    assert response == "Test response"
    mock_openai_client.chat.completions.create.assert_called_once()


def test_llm_router_does_not_log_think_content(test_settings, monkeypatch):
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = "<think>private reasoning should stay private</think>Hello world"
    client.chat.completions.create.return_value = mock_response
    logger_mock = MagicMock()
    monkeypatch.setattr("reborn_core.infrastructure.brain.llm_router.logger", logger_mock)

    router = LLMRouter(app_settings=test_settings, client=client)
    response = router.generate_response([{"role": "user", "content": "hello"}])

    logged_debug_args = " ".join(
        str(arg) for call in logger_mock.debug.call_args_list for arg in call.args
    )
    assert response == "Hello world"
    assert "private reasoning should stay private" not in logged_debug_args


def test_llm_router_retry_logic(test_settings, mock_openai_client):
    # Mock failure then success
    mock_openai_client.chat.completions.create.side_effect = [
        Exception("API Error"),
        mock_openai_client.chat.completions.create.return_value,
    ]

    router = LLMRouter(app_settings=test_settings, client=mock_openai_client)
    msgs = [{"role": "user", "content": "hello"}]

    # Tenacity retry timing is hardcoded here, so this test exercises the real retry path.
    # For now, let's just assert it eventually succeeds.
    response = router.generate_response(msgs)
    assert response == "Test response"
    assert mock_openai_client.chat.completions.create.call_count == 2


def test_stt_engine_transcribe(test_settings):
    mock_model = MagicMock()
    mock_model.generate.return_value = [{"text": "Hello world"}]

    engine = STTEngine(app_settings=test_settings, model=mock_model)
    result = engine.transcribe_audio_bytes(b"dummy audio data")

    assert result == "Hello world"
    mock_model.generate.assert_called_once()
    call_kwargs = mock_model.generate.call_args.kwargs
    assert call_kwargs["batch_size_s"] == 300
    assert call_kwargs["disable_pbar"] is True
    assert not Path(call_kwargs["input"]).exists()


def test_stt_engine_sets_modelscope_cache_from_settings(test_settings, monkeypatch):
    settings = test_settings.model_copy(update={"modelscope_cache_dir": Path("data/ms-cache")})
    monkeypatch.delenv("MODELSCOPE_CACHE", raising=False)

    STTEngine(app_settings=settings, model=MagicMock())

    assert os.environ["MODELSCOPE_CACHE"] == str(settings.resolved_modelscope_cache_dir)
    assert settings.resolved_modelscope_cache_dir.exists()


def test_stt_engine_builds_funasr_model_from_settings(test_settings):
    mock_model = MagicMock()
    model_factory = MagicMock(return_value=mock_model)
    settings = test_settings.model_copy(
        update={
            "stt_model_name": "custom-asr",
            "funasr_vad_model_name": "custom-vad",
            "funasr_punc_model_name": "custom-punc",
        }
    )

    engine = STTEngine(app_settings=settings, model_factory=model_factory)

    assert engine.model is mock_model
    model_factory.assert_called_once_with(
        model="custom-asr",
        vad_model="custom-vad",
        punc_model="custom-punc",
        disable_update=True,
    )


def test_stt_engine_empty_input(test_settings):
    engine = STTEngine(app_settings=test_settings, model=MagicMock())
    assert engine.transcribe_audio_bytes(b"") == ""


def test_stt_engine_local_rejects_whisper_model_name(test_settings):
    settings = test_settings.model_copy(update={"stt_model_name": "whisper-1"})

    with pytest.raises(ConfigurationError, match="requires a FunASR model name"):
        STTEngine(app_settings=settings, model=MagicMock())


def test_stt_engine_local_whisper_engine_is_reserved(test_settings):
    settings = test_settings.model_copy(
        update={"stt_local_engine": "whisper", "stt_model_name": "small"}
    )

    with pytest.raises(ConfigurationError, match="reserved for future local Whisper support"):
        STTEngine(app_settings=settings, model=MagicMock())


def test_stt_engine_failure_handling(test_settings):
    mock_model = MagicMock()
    mock_model.generate.side_effect = Exception("Model crash")

    engine = STTEngine(app_settings=test_settings, model=mock_model)

    with pytest.raises(InfrastructureError, match="本地语音转写失败: Model crash"):
        engine.transcribe_audio_bytes(b"dummy data")


def test_stt_engine_cloud_requires_api_key(test_settings):
    settings = test_settings.model_copy(
        update={
            "stt_endpoint": "https://api.openai.com/v1",
            "stt_api_key": None,
            "stt_model_name": "whisper-1",
        }
    )

    with pytest.raises(ConfigurationError, match="Cloud STT requires STT_API_KEY"):
        STTEngine(app_settings=settings)


def test_stt_engine_cloud_transcribes_with_openai_compatible_client(test_settings):
    transcription_client = MagicMock()
    transcription_client.audio.transcriptions.create.return_value = MagicMock(
        text="Cloud transcript"
    )
    settings = test_settings.model_copy(
        update={
            "stt_endpoint": "https://api.openai.com/v1",
            "stt_api_key": "sk-test",
            "stt_model_name": "whisper-1",
        }
    )

    engine = STTEngine(app_settings=settings, transcription_client=transcription_client)
    result = engine.transcribe_audio_bytes(b"dummy audio data")

    assert result == "Cloud transcript"
    transcription_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = transcription_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["file"].closed
    assert not Path(call_kwargs["file"].name).exists()
