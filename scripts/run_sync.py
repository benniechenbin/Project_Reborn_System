import os
import sys
from datetime import datetime
from utils.logger import logger
from config.settings import settings
from backend.obsidian.injector import ObsidianInjector
from utils.scanner import AssetScanner
from backend.database.db_manager import DBManager

# 动态路径处理
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def fetch_real_metrics():
    """从硬盘和数据库获取真实的统计数据"""
    # 1. 实例化扫描器 (确保你的 .env 里配置了这两个路径)
    # 假设你在 .env 里有 AUDIO_DATA_PATH
    audio_path = os.getenv("AUDIO_DATA_PATH", os.path.join(project_root, "data/audio/raw"))
    scanner = AssetScanner(
        obsidian_path=settings.active_obsidian_path,
        audio_path=audio_path
    )
    
    # 2. 执行真实扫描
    notes_count, word_count = scanner.count_notes_and_words()
    audio_duration = scanner.count_audio_duration()
    
    metrics = {
        'audio_duration': audio_duration,
        'notes_count': notes_count,
        'word_count': word_count,
        'sync_time': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    return metrics

if __name__ == "__main__":
    logger.info("🚀 启动 [Project Reborn] 真实数据同步...")
    
    vault_path = settings.active_obsidian_path
    if not vault_path:
        logger.error("未配置 Obsidian 路径，请检查 .env")
        sys.exit(1)

    # 1. 获取真实数据
    metrics = fetch_real_metrics()
    
    # 2. 存入数据库历史
    db = DBManager()
    db.save_sync_record(metrics)
    
    # 3. 注入 Obsidian 仪表盘
    injector = ObsidianInjector(vault_path=vault_path)
    # 注意：确保 01_Project_Plan.md 放在库的根目录，或者写对相对路径
    success = injector.update_metrics('01_Project_Plan.md', metrics)
    
    if success:
        logger.info(f"✨ 同步成功！当前资产：{metrics['notes_count']}篇笔记 / {metrics['audio_duration']}分钟语音")
    else:
        logger.warning("同步完成但注入文档失败，请检查锚点。")