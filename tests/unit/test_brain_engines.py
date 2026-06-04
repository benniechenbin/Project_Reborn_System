import pytest
from unittest.mock import MagicMock
from reborn_core.domains.brain.llm_router import LLMRouter
from reborn_core.domains.brain.stt_engine import STTEngine


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


def test_llm_router_retry_logic(test_settings, mock_openai_client):
    # Mock failure then success
    mock_openai_client.chat.completions.create.side_effect = [
        Exception("API Error"),
        mock_openai_client.chat.completions.create.return_value,
    ]

    router = LLMRouter(app_settings=test_settings, client=mock_openai_client)
    msgs = [{"role": "user", "content": "hello"}]

    # We need to reduce wait time for tests if possible, but tenacity retry is hardcoded in the class.
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


def test_stt_engine_empty_input(test_settings):
    engine = STTEngine(app_settings=test_settings, model=MagicMock())
    assert engine.transcribe_audio_bytes(b"") == ""


def test_stt_engine_failure_handling(test_settings):
    mock_model = MagicMock()
    mock_model.generate.side_effect = Exception("Model crash")

    engine = STTEngine(app_settings=test_settings, model=mock_model)
    result = engine.transcribe_audio_bytes(b"dummy data")

    assert result == ""
