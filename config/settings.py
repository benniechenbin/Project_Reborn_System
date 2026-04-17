import platform
import os
from utils.logger import logger
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    """全局系统配置中心"""
    
    # 基础存储配置
    db_path: str = Field(default="data/sqlite/reborn.db", description="SQLite数据库路径")
    vector_db_path: str = Field(default="data/qdrant_db", description="向量数据库存储目录")
    # Obsidian 跨端路径
    obsidian_vault_path_mac: str = Field(default="", description="Mac端iCloud路径")
    obsidian_vault_path_win: str = Field(default="", description="Windows端iCloud路径")
    
    # 录音资产跨端路径
    audio_data_path_mac: str = Field(default="", description="Mac端录音iCloud路径")
    audio_data_path_win: str = Field(default="", description="Windows端录音iCloud路径")

    # Project Reborn 专属扫描白名单 (边界上下文)
    REBORN_TARGET_FOLDERS: list = [
        "02_Values",
        "03_Stories"
    ]

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding='utf-8',
        extra='ignore' 
    )
    def __init__(self, **values):
        super().__init__(**values)       
        Path(self.vector_db_path).mkdir(parents=True, exist_ok=True)
        # 顺便加一句打印，启动时验证路径是否加载成功
        logger.info(f"✅ 当前激活的 Obsidian 路径: {self.active_obsidian_path}")
    @property
    def active_obsidian_path(self) -> str:
        """智能返回当前操作系统的 Obsidian 路径"""
        os_name = platform.system()
        if os_name == "Darwin":
            return self.obsidian_vault_path_mac
        elif os_name == "Windows":
            return self.obsidian_vault_path_win
        else:
            logger.error(f"未知的操作系统: {os_name}") 
            return ""

    # 智能音频路径路由
    @property
    def active_audio_path(self) -> str:
        """智能返回当前操作系统的录音路径"""
        os_name = platform.system()
        if os_name == "Darwin":
            return self.audio_data_path_mac
        elif os_name == "Windows":
            return self.audio_data_path_win
        else:
            logger.error(f"未知的操作系统: {os_name}")
            return ""

# 暴露单例实例供全局调用
settings = Settings()