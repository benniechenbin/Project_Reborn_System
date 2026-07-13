import os
import platform
from pathlib import Path
from typing import Literal, Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from reborn_core.domains import LegacyActivationMode


def find_project_root(
    current_path: Path,
    markers: tuple[str, ...] = ("pyproject.toml", "requirements.txt", ".git"),
) -> Path:
    if env_root := os.environ.get("PROJECT_ROOT"):
        return Path(env_root).resolve()
    for parent in current_path.parents:
        if any((parent / marker).exists() for marker in markers):
            return parent
    return current_path.parent


BASE_DIR = find_project_root(Path(__file__).resolve())


LogFormat = Literal["auto", "pretty", "json"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
AppEnv = Literal["development", "dev", "test", "production", "prod"]
STTLocalEngine = Literal["funasr", "whisper"]


# 默认值（必须在 class 外部定义，才能被 Field 引用）
DEFAULT_APP_ENV: AppEnv = "dev"
DEFAULT_LOG_LEVEL: LogLevel = "DEBUG"
DEFAULT_LOG_FORMAT: LogFormat = "auto"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    base_dir: Path = Field(
        default=BASE_DIR,
        description="项目根目录",
    )
    app_name: str = Field(
        default="Project Reborn",
        description="应用名称",
    )
    app_version: str = Field(
        default="0.1.0",
        description="应用版本",
    )
    app_env: AppEnv = Field(
        default=DEFAULT_APP_ENV,
        description="应用环境",
    )
    log_dir: Path = Field(
        default=Path("logs"),
        description="日志目录",
    )
    log_level: LogLevel = Field(
        default=DEFAULT_LOG_LEVEL,
        description="日志级别",
    )
    log_format: LogFormat = Field(
        default=DEFAULT_LOG_FORMAT,
        description="日志格式：auto 根据环境选择，pretty 为开发可读格式，json 为结构化日志。",
    )

    models_dir: Path = Field(default=Path("data/local_models"), description="本地模型目录")
    hf_mirror: str = Field(default="https://hf-mirror.com", description="HuggingFace 镜像地址")
    db_path: Path = Field(default=Path("data/sqlite/reborn.db"), description="SQLite 数据库路径")
    vector_db_path: Path = Field(default=Path("data/retrieval"), description="检索索引根目录")
    backup_dir: Path = Field(default=Path("data/backups"), description="加密备份目录")
    memory_gaps_path: Path = Field(
        default=Path("data/memory_gaps.json"),
        description="RAG 记忆盲区记录文件路径",
    )
    project_profile_path: Path = Field(
        default=Path("data/project_profile.toml"),
        description="Project Reborn 家庭资料 TOML 文件路径",
    )
    task_worker_threads: int = Field(default=2, ge=1, le=16, description="后台任务工作线程数")
    retrieval_generation_retention: int = Field(
        default=3,
        ge=2,
        le=20,
        description="保留的可用检索索引代次数量",
    )

    backup_encryption_key: SecretStr | None = Field(
        default=None,
        description="用于加密备份归档的 Fernet 密钥",
    )
    backup_require_encryption: bool = Field(
        default=True,
        description="是否拒绝创建未加密的明文备份",
    )
    access_policy_backend: str = Field(
        default="local_owner",
        description="访问策略适配器；当前单用户默认值为 local_owner",
    )
    legacy_activation_mode: LegacyActivationMode = Field(
        default=LegacyActivationMode.OWNER_ONLY,
        description="数字遗产激活规则",
    )
    legacy_activation_file: Path = Field(
        default=Path("data/governance/legacy_activation.json"),
        description="数字遗产激活凭证文件路径",
    )

    obsidian_vault_path_mac: Path | None = Field(
        default=None, description="macOS 的 Obsidian 仓库路径"
    )
    obsidian_vault_path_win: Path | None = Field(
        default=None, description="Windows 的 Obsidian 仓库路径"
    )
    audio_data_path_mac: Path | None = Field(default=None, description="macOS 的音频资料路径")
    audio_data_path_win: Path | None = Field(default=None, description="Windows 的音频资料路径")

    llm_base_url: str = Field(
        default="https://api.deepseek.com", description="大语言模型 API 基础地址"
    )
    llm_api_key: SecretStr | None = Field(default=None, description="大语言模型 API 密钥")
    llm_model_name: str = Field(default="deepseek-chat", description="大语言模型名称")

    stt_endpoint: str = Field(
        default="local",
        description=(
            "STT 入口；设为 local 使用本地 FunASR，或填写 OpenAI-compatible base URL，"
            "例如 https://api.openai.com/v1 切换云端转写。"
        ),
    )
    stt_api_key: SecretStr | None = Field(default=None, description="语音转文字 API 密钥")
    stt_model_name: str = Field(
        default="paraformer-zh",
        description="语音转文字模型名称；本地模式为 FunASR 主模型名，云端模式为转写模型名",
    )
    stt_local_engine: STTLocalEngine = Field(
        default="funasr",
        description="本地 STT 引擎；当前实现 funasr，whisper 为预留配置",
    )
    funasr_vad_model_name: str | None = Field(
        default="fsmn-vad",
        description="FunASR VAD 模型名称；留空则禁用 VAD",
    )
    funasr_punc_model_name: str | None = Field(
        default="ct-punc",
        description="FunASR 标点模型名称；留空则禁用标点恢复",
    )
    modelscope_cache_dir: Path = Field(
        default=Path("data/local_models"),
        description="ModelScope/FunASR 模型缓存目录",
    )

    core_values_folder: str = Field(
        default="02_Values",
        description="价值观和身份核所在的 Obsidian 目录名",
    )
    stories_folder: str = Field(
        default="03_Stories",
        description="人生故事记忆所在的 Obsidian 目录名",
    )
    ai_reflections_folder: str = Field(
        default="00_AI_Reflections",
        description="AI 派生价值观反思所在的子目录名",
    )
    source_artifacts_folder: str = Field(
        default="01_Source_Artifacts",
        description="不可变原始资料归档目录名",
    )
    REBORN_TARGET_FOLDERS: tuple[str, ...] = Field(
        default=("02_Values", "03_Stories"),
        description="需要摄入检索索引的 Obsidian 目录",
    )

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "obsidian_vault_path_mac",
        "obsidian_vault_path_win",
        "audio_data_path_mac",
        "audio_data_path_win",
        "funasr_vad_model_name",
        "funasr_punc_model_name",
        mode="before",
    )
    @classmethod
    def empty_path_is_none(cls, value: Any) -> Any:
        return None if value == "" else value

    @property
    def active_obsidian_path(self) -> Path | None:
        if platform.system() == "Darwin":
            return self.obsidian_vault_path_mac
        if platform.system() == "Windows":
            return self.obsidian_vault_path_win
        return None

    @property
    def active_audio_path(self) -> Path | None:
        if platform.system() == "Darwin":
            return self.audio_data_path_mac
        if platform.system() == "Windows":
            return self.audio_data_path_win
        return None

    @property
    def resolved_log_dir(self) -> Path:
        return self._resolve_path(self.log_dir)

    @property
    def resolved_models_dir(self) -> Path:
        return self._resolve_path(self.models_dir)

    @property
    def resolved_db_path(self) -> Path:
        return self._resolve_path(self.db_path)

    @property
    def resolved_vector_db_path(self) -> Path:
        return self._resolve_path(self.vector_db_path)

    @property
    def resolved_backup_dir(self) -> Path:
        return self._resolve_path(self.backup_dir)

    @property
    def resolved_memory_gaps_path(self) -> Path:
        return self._resolve_path(self.memory_gaps_path)

    @property
    def resolved_project_profile_path(self) -> Path:
        return self._resolve_path(self.project_profile_path)

    @property
    def resolved_legacy_activation_file(self) -> Path:
        return self._resolve_path(self.legacy_activation_file)

    @property
    def resolved_modelscope_cache_dir(self) -> Path:
        return self._resolve_path(self.modelscope_cache_dir)

    @property
    def memory_index_folders(self) -> tuple[str, ...]:
        default_folders = ("02_Values", "03_Stories")
        if tuple(self.REBORN_TARGET_FOLDERS) != default_folders:
            return self.REBORN_TARGET_FOLDERS
        return (self.core_values_folder, self.stories_folder)

    def _resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.base_dir / path
