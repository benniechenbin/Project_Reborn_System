from pathlib import Path
from reborn_core.core.config import settings
from reborn_core.core.logger import logger, setup_logger

def init_system():
    """
    🌌 Project Reborn 引擎点火程序
    负责：初始化日志、创建所有必须的物理挂载目录、环境预检
    此函数必须在程序的绝对起点被调用！
    """
    log_dir = setup_logger(log_dir=settings.resolved_log_dir)

    logger.info("="*50)
    logger.info("🚀 Project Reborn 引擎正在执行点火序列...")  

    paths_to_create = [
        log_dir,
        settings.models_dir,
        settings.db_path.parent,
        settings.vector_db_path
    ]
    
    for p in paths_to_create:        
        p.mkdir(parents=True, exist_ok=True)
        logger.debug(f"📁 挂载系统目录: {p}")
        
    # 3. 预检：系统状态播报
    try:
        active_obsidian = settings.active_obsidian_path
        logger.info(f"📂 锚定 Obsidian 知识库: {active_obsidian}")
    except RuntimeError as e:
        logger.error(f"❌ 致命错误：{e}")
        raise e
        
    logger.info(f"💾 关系型大脑 (SQLite): {settings.db_path}")
    logger.info(f"🧠 潜意识引擎 (Qdrant): {settings.vector_db_path}")
    logger.info(f"💬 大语言中枢: {settings.llm_model_name} (@{settings.llm_base_url})")
    
    logger.info("✅ 引擎点火完成，系统各项指标正常！")
    logger.info("="*50)