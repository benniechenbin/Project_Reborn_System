import logging
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

def setup_logger(name="Project_Reborn"):
    """
    配置全局日志器：同时输出到控制台和 logs/ 文件夹
    """
    # 1. 创建日志文件夹
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    # 2. 生成以日期命名的日志文件名
    log_filename = f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_path = log_dir / log_filename

    # 3. 创建日志格式 (时间 - 模块名 - 级别 - 消息)
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
        datefmt='%H:%M:%S'
    )

    # 4. 初始化 Logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False   

    # 防止重复添加 Handler（多次调用 setup_logger 时避免日志翻倍）
    if not logger.handlers:
                # 控制台 Handler (彩色输出建议)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

        # 文件 Handler (持久化存储)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    return logger

# 创建一个默认的 logger 实例方便直接导入使用
logger = setup_logger()