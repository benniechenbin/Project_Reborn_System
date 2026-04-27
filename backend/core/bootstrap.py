from pathlib import Path
from backend.config.settings import settings
from backend.observability.logger import setup_logger, logger

def init_system():
    """
    🌌 Project Reborn 引擎点火程序
    负责：初始化日志、创建所有必须的物理挂载目录、环境预检
    此函数必须在程序的绝对起点被调用！
    """
    # 1. 点火：日志系统引导
    # 获取项目根目录
    project_root = Path(__file__).resolve().parent.parent.parent
    log_dir = project_root / "logs"
    
    # 初始化 Loguru 日志中心
    setup_logger(log_dir=log_dir, log_level="INFO")

    logger.info("="*50)
    logger.info("🚀 Project Reborn 引擎正在执行点火序列...")

    # 2. 预检：创建核心物理目录 (如果缺失)
    sqlite_dir = Path(settings.db_path).parent
    vector_dir = Path(settings.vector_db_path)
    local_models_dir = project_root / "data" / "local_models"

    paths_to_create = [
        log_dir,
        sqlite_dir,
        vector_dir,
        local_models_dir
    ]
    
    for p in paths_to_create:        
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            logger.debug(f"📁 已创建系统目录: {p}")

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