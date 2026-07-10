import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from reborn_core.config import Settings
from reborn_core.core.exceptions import ConfigurationError, InfrastructureError
from reborn_core.observability import logger


class STTEngine:
    def __init__(
        self,
        app_settings: Settings,
        model: Any | None = None,
        model_factory: Callable[..., Any] | None = None,
        transcription_client: Any | None = None,
    ) -> None:
        self.settings = app_settings
        self.endpoint = app_settings.stt_endpoint.strip()
        self.model_name = app_settings.stt_model_name.strip()
        self.model: Any | None = None
        self.transcription_client = None

        if _is_local_endpoint(self.endpoint):
            _validate_local_engine(app_settings.stt_local_engine)
            self.model = self._build_local_funasr_model(app_settings, model, model_factory)
            return

        if not _is_url_endpoint(self.endpoint):
            raise ConfigurationError(
                "STT_ENDPOINT must be 'local' or an OpenAI-compatible base URL "
                "(for example https://api.openai.com/v1)."
            )

        self.transcription_client = self._build_cloud_client(app_settings, transcription_client)
        logger.info(f"☁️ 云端 STT 已配置：endpoint={self.endpoint}, model={self.model_name}")

    def _build_local_funasr_model(
        self,
        app_settings: Settings,
        model: Any | None,
        model_factory: Callable[..., Any] | None,
    ) -> Any:
        _validate_local_model_name(self.model_name)
        cache_dir = _configure_modelscope_cache(app_settings.resolved_modelscope_cache_dir)
        _warn_if_funasr_cache_is_empty(cache_dir)
        logger.info("⏳ 准备加载达摩 ASR...")
        logger.info(f"📁 ModelScope 缓存路径已锁定至: {cache_dir}")

        if model is not None:
            logger.info("✅ 达摩 ASR 准备完毕！本地隐私听觉已完全激活。")
            return model

        try:
            if model_factory is None:
                from funasr import AutoModel

                model_factory = AutoModel
            model = model_factory(**_funasr_model_kwargs(app_settings))
        except Exception as exc:
            logger.exception("FunASR 初始化失败")
            raise InfrastructureError(f"本地 FunASR 初始化失败: {exc}") from exc
        logger.info("✅ 达摩 ASR 准备完毕！本地隐私听觉已完全激活。")
        return model

    def _build_cloud_client(self, app_settings: Settings, transcription_client: Any | None) -> Any:
        if transcription_client is not None:
            return transcription_client
        if app_settings.stt_api_key is None:
            raise ConfigurationError("Cloud STT requires STT_API_KEY.")
        try:
            from openai import OpenAI

            return OpenAI(
                api_key=app_settings.stt_api_key.get_secret_value(),
                base_url=self.endpoint,
            )
        except Exception as exc:
            logger.exception("云端 STT 客户端初始化失败")
            raise InfrastructureError(f"云端 STT 客户端初始化失败: {exc}") from exc

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        """将前端传来的音频字节流转换为文字"""
        if not audio_bytes:
            return ""

        if _is_local_endpoint(self.endpoint):
            return self._transcribe_local_funasr(audio_bytes)
        return self._transcribe_cloud(audio_bytes)

    def _transcribe_local_funasr(self, audio_bytes: bytes) -> str:
        tmp_path = ""
        try:
            logger.info("👂 接收到音频流，开始本地离线解析...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name

            if self.model is None:
                raise RuntimeError("Local FunASR model is not initialized")
            result = self.model.generate(input=tmp_path, batch_size_s=300, disable_pbar=True)
            transcript_text = _extract_transcript_text(result)
            logger.info(f"✅ 语音解析完成，文本长度: {len(transcript_text)}")
            return transcript_text
        except Exception as exc:
            logger.exception("本地语音解析失败")
            raise InfrastructureError(f"本地语音转写失败: {exc}") from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning(f"无法清理临时音频文件: {tmp_path}")

    def _transcribe_cloud(self, audio_bytes: bytes) -> str:
        tmp_path = ""
        try:
            logger.info("☁️ 接收到音频流，开始云端转写...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name

            if self.transcription_client is None:
                raise RuntimeError("Cloud STT client is not initialized")
            with open(tmp_path, "rb") as audio_file:
                result = self.transcription_client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.model_name,
                )
            transcript_text = _extract_transcript_text(result)
            logger.info(f"✅ 云端语音解析完成，文本长度: {len(transcript_text)}")
            return transcript_text
        except Exception as exc:
            logger.exception("云端语音解析失败")
            raise InfrastructureError(f"云端语音转写失败: {exc}") from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning(f"无法清理临时音频文件: {tmp_path}")


def _configure_modelscope_cache(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MODELSCOPE_CACHE"] = str(cache_dir)
    return cache_dir


def _warn_if_funasr_cache_is_empty(cache_dir: Path) -> None:
    if not any(cache_dir.rglob("config.yaml")):
        logger.warning(
            "未检测到 FunASR 本地模型缓存；首次转写可能需要从 ModelScope 下载 ASR 模型。"
        )


def _funasr_model_kwargs(app_settings: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": app_settings.stt_model_name,
        "disable_update": True,
    }
    if app_settings.funasr_vad_model_name:
        kwargs["vad_model"] = app_settings.funasr_vad_model_name
    if app_settings.funasr_punc_model_name:
        kwargs["punc_model"] = app_settings.funasr_punc_model_name
    return kwargs


def _extract_transcript_text(result: Any) -> str:
    parts: list[str] = []
    _collect_transcript_parts(result, parts)
    return " ".join(part for part in parts if part).strip()


def _collect_transcript_parts(value: Any, parts: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        parts.append(value.strip())
        return
    if isinstance(value, dict):
        text = value.get("text")
        if text is not None:
            parts.append(str(text).strip())
        return
    text = getattr(value, "text", None)
    if text is not None:
        parts.append(str(text).strip())
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _collect_transcript_parts(item, parts)


def _is_local_endpoint(endpoint: str) -> bool:
    return endpoint.lower() == "local"


def _is_url_endpoint(endpoint: str) -> bool:
    return endpoint.startswith(("http://", "https://"))


def _validate_local_model_name(model_name: str) -> None:
    if model_name.lower() in {"whisper", "whisper-1"}:
        raise ConfigurationError(
            "STT_ENDPOINT=local with STT_LOCAL_ENGINE=funasr requires a FunASR model name. "
            "Set STT_MODEL_NAME=paraformer-zh "
            "for local FunASR, or set STT_ENDPOINT to an OpenAI-compatible URL for whisper-1."
        )


def _validate_local_engine(local_engine: str) -> None:
    if local_engine == "funasr":
        return
    if local_engine == "whisper":
        raise ConfigurationError(
            "STT_LOCAL_ENGINE=whisper is reserved for future local Whisper support; "
            "the current local implementation only supports STT_LOCAL_ENGINE=funasr."
        )
    raise ConfigurationError(f"Unsupported STT_LOCAL_ENGINE: {local_engine}")
