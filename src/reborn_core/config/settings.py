import platform
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .enums import LegacyActivationMode


def find_project_root(
    current_path: Path,
    markers: tuple[str, ...] = ("pyproject.toml", ".git"),
) -> Path:
    for parent in [current_path] + list(current_path.parents):
        if any((parent / marker).exists() for marker in markers):
            return parent
    return current_path.parent


BASE_DIR = find_project_root(Path(__file__).resolve())


class Settings(BaseSettings):
    """经过校验的应用配置；导入模块时不会创建任何外部资源。"""

    base_dir: Path = Field(default=BASE_DIR, description="项目根目录")

    app_name: str = Field(default="Project Reborn", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    app_env: str = Field(default="dev", description="应用环境")

    log_dir: Path = Field(default=Path("logs"), description="日志目录")
    log_level: str = Field(default="DEBUG", description="日志级别")

    models_dir: Path = Field(default=Path("data/local_models"), description="本地模型目录")
    hf_mirror: str = Field(default="https://hf-mirror.com", description="HuggingFace 镜像地址")
    db_path: Path = Field(default=Path("data/sqlite/reborn.db"), description="SQLite 数据库路径")
    vector_db_path: Path = Field(default=Path("data/retrieval"), description="检索索引根目录")
    backup_dir: Path = Field(default=Path("data/backups"), description="加密备份目录")
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

    stt_base_url: str = Field(
        default="https://api.openai.com/v1", description="语音转文字 API 基础地址"
    )
    stt_api_key: SecretStr | None = Field(default=None, description="语音转文字 API 密钥")
    stt_model_name: str = Field(default="whisper-1", description="语音转文字模型名称")

    child_name: str | None = Field(default=None, description="孩子姓名")
    child_nickname: str | None = Field(default=None, description="孩子昵称")
    child_gender: str | None = Field(default=None, description="孩子性别")
    child_birthday: str | None = Field(default=None, description="孩子生日（YYYY-MM-DD）")

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
    def resolved_legacy_activation_file(self) -> Path:
        return self._resolve_path(self.legacy_activation_file)

    def require_child_profile(self) -> tuple[str, str, str, str]:
        values = (
            self.child_name,
            self.child_nickname,
            self.child_gender,
            self.child_birthday,
        )
        if not all(values):
            raise ValueError(
                "Avatar sandbox requires CHILD_NAME, CHILD_NICKNAME, "
                "CHILD_GENDER and CHILD_BIRTHDAY."
            )
        return values  # type: ignore[return-value]

    def _resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.base_dir / path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
