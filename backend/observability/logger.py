import sys
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from backend.config.settings import settings


def setup_logger(
    log_dir: Path | None = None,
    log_level: str | None = None,
    log_file_name: str = "system_{time:YYYY-MM-DD}.log",
) -> Path:
    """
    配置控制台日志和文件日志。

    返回实际使用的日志目录。
    """
    target_dir = log_dir or settings.resolved_log_dir
    target_level = log_level or settings.log_level
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stdout,
        level=target_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    logger.add(
        target_dir / log_file_name,
        rotation="00:00",
        retention="30 days",
        level=target_level,
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )

    return target_dir


def add_custom_file(
    file_name: str,
    log_dir: Path | None = None,
    level: str = "INFO",
    filter_rule: str | Callable | None = None,
) -> int:
    """
    运行时添加一个额外的文件日志输出，并返回对应的 handler id。
    """
    target_dir = log_dir or settings.resolved_log_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    handler_id = logger.add(
        target_dir / file_name,
        level=level,
        rotation="10 MB",
        filter=filter_rule,
    )
    return handler_id
