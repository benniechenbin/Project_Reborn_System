import platform
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Settings(BaseSettings):
    """全局系统配置中心"""
    
    # 基础存储配置
    db_path: str = Field(default="data/sqlite/reborn.db", description="SQLite数据库路径")
    
    # Obsidian 跨端路径 (在 .env 中配置)
    obsidian_vault_path_mac: str = Field(default="", description="Mac端iCloud路径")
    obsidian_vault_path_win: str = Field(default="", description="Windows端iCloud路径")
    
    # 未来可随时在此处追加：gemini_api_key, sovits_url 等

    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8',
        extra='ignore' 
    )

    @property
    def active_obsidian_path(self) -> str:
        """智能返回当前操作系统的 Obsidian 路径"""
        os_name = platform.system()
        if os_name == "Darwin":
            return self.obsidian_vault_path_mac
        elif os_name == "Windows":
            return self.obsidian_vault_path_win
        else:
            logging.error(f"未知的操作系统: {os_name}")
            return ""

# 暴露单例实例供全局调用
settings = Settings()