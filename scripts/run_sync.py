import os
import sys
from datetime import datetime

# 动态路径处理 (置顶)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(os.path.join(project_root, "src"))

# from reborn_core.core.bootstrap import init_system
# init_system()

from src.reborn_core.core.config import settings
from src.reborn_core.infrastructure.knowledge import AssetScanner, load_processed_knowledge
from src.reborn_core.domains.memory.relational import DBManager
from src.reborn_core.domains.memory.vector_store import QdrantDBProvider
from src.reborn_core.core.logger import logger

def fetch_real_metrics():
    """从硬盘获取真实的统计数据（保持原样）"""
    scanner = AssetScanner(
        obsidian_path=settings.active_obsidian_path,
        audio_path=settings.active_audio_path 
    )
    notes_count, word_count = scanner.count_notes_and_words()
    audio_duration = scanner.count_audio_duration()
    
    return {
        'audio_duration': audio_duration,
        'notes_count': notes_count,
        'word_count': word_count,
        'sync_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def execute_full_sync():
    """✨ 终极摄入引擎：统计指标 + 向量化存储"""
    logger.info("🚀 开始执行全量数据同步与记忆摄入...")
    
    # 1. 扫描获取基本指标
    metrics = fetch_real_metrics()
    
    # 2. 核心大动脉接通：读取并切片 Obsidian 笔记
    logger.info("🧠 正在提取并切片核心记忆...")
    docs_to_embed = load_processed_knowledge()
    
    if docs_to_embed:
        qdrant_db = QdrantDBProvider()
        logger.info("🧹 正在清理旧向量库，准备执行全量重建...")
        qdrant_db.clear()         

        logger.info(f"🧬 准备将 {len(docs_to_embed)} 个记忆碎片注入...")
        qdrant_db.add_documents(docs_to_embed)
        logger.info("✅ 记忆库已完成全量重建！")
    else:
        logger.warning("⚠️ 未发现可用的记忆碎片，跳过向量化阶段。")
        
    # 4. 保存统计快照到 SQLite
    db = DBManager()
    db.save_sync_record(metrics)
    
    return metrics

if __name__ == "__main__":
    # 如果直接在终端运行脚本，则执行同步
    execute_full_sync()