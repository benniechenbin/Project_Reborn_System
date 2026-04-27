import platform
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    """全局系统配置中心 (纯净版：无副作用，无外部依赖)"""
    
    # 基础存储配置
    db_path: str = Field(default="data/sqlite/reborn.db", description="SQLite数据库路径")
    vector_db_path: str = Field(default="data/qdrant_db", description="向量数据库存储目录")
    
    # Obsidian 跨端路径
    obsidian_vault_path_mac: str = Field(default="", description="Mac端iCloud路径")
    obsidian_vault_path_win: str = Field(default="", description="Windows端iCloud路径")
    
    # 录音资产跨端路径
    audio_data_path_mac: str = Field(default="", description="Mac端录音iCloud路径")
    audio_data_path_win: str = Field(default="", description="Windows端录音iCloud路径")

    # 大模型中枢 (LLM) API 配置
    llm_base_url: str = Field(default="https://api.deepseek.com", description="大模型 API Base URL")
    llm_api_key: str = Field(default="", description="大模型 API Key")
    llm_model_name: str = Field(default="deepseek-chat", description="大模型名称")

    # Project Reborn 专属扫描白名单
    REBORN_TARGET_FOLDERS: list = [
        "02_Values",
        "03_Stories"
    ]

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding='utf-8',
        extra='ignore' 
    )

    # 🚨 删除了 __init__ 方法中的 mkdir 和 logger.info

    @property
    def active_obsidian_path(self) -> str:
        """智能返回当前操作系统的 Obsidian 路径"""
        os_name = platform.system()
        if os_name == "Darwin":
            return self.obsidian_vault_path_mac
        elif os_name == "Windows":
            return self.obsidian_vault_path_win
        else:
            # 🚨 解耦点：遇到严重错误直接抛出系统级异常，让最上层的捕获机制或启动脚本去报错
            raise RuntimeError(f"不受支持的操作系统: {os_name}。Project Reborn 目前仅支持 Mac/Windows。")

    @property
    def active_audio_path(self) -> str:
        """智能返回当前操作系统的录音路径"""
        os_name = platform.system()
        if os_name == "Darwin":
            return self.audio_data_path_mac
        elif os_name == "Windows":
            return self.audio_data_path_win
        else:
            raise RuntimeError(f"不受支持的操作系统: {os_name}。")

# 暴露单例实例供全局调用
settings = Settings()