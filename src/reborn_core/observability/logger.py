from __future__ import annotations

import contextvars
import sys
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

__all__ = [
    "add_custom_file",
    "get_trace_id",
    "logger",
    "set_trace_id",
    "setup_logger",
    "shutdown_logger",
    "trace_context",
    "trace_id_var",
]

if TYPE_CHECKING:
    from loguru import Record

# 全局追踪 ID 变量
trace_id_var = contextvars.ContextVar("trace_id", default="system")


def _patch_record(record: Record) -> None:
    record["extra"].update(trace_id=trace_id_var.get())


def setup_logger(
    log_dir: Path | str = Path("logs"),
    log_level: str = "INFO",
    log_format: str = "auto",
    app_env: str = "development",
    log_prefix: str = "system",
) -> Path:
    """配置日志系统，支持控制台彩色输出、文件滚动记录以及可选的 JSON 格式。"""
    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    target_level = log_level or "INFO"
    env_str = app_env.lower()
    format_str = log_format.lower()

    if format_str not in {"auto", "pretty", "json"}:
        raise ValueError(
            f"Invalid log_format: {log_format!r}. Must be one of: 'auto', 'pretty', 'json'."
        )

    if format_str == "json":
        use_json_logs = True
    elif format_str == "pretty":
        use_json_logs = False
    else:  # "auto"
        use_json_logs = env_str in ("production", "prod")

    is_development = env_str in ("development", "dev")

    logger.remove()
    logger.configure(patcher=_patch_record)

    if use_json_logs:
        logger.add(
            sys.stdout,
            level=target_level,
            serialize=True,
            enqueue=True,
        )
        logger.add(
            target_dir / f"{log_prefix}_{{time:YYYY-MM-DD}}.jsonl",
            rotation="00:00",
            retention="30 days",
            level=target_level,
            serialize=True,
            enqueue=True,
        )
        return target_dir

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<magenta>trace_id={extra[trace_id]}</magenta> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        "trace_id={extra[trace_id]} | {name}:{line} - {message}"
    )

    logger.add(
        sys.stdout,
        level=target_level,
        colorize=is_development,
        format=console_format,
    )
    logger.add(
        target_dir / f"{log_prefix}_{{time:YYYY-MM-DD}}.log",
        rotation="00:00",
        retention="30 days",
        level=target_level,
        enqueue=True,
        format=file_format,
    )

    return target_dir


def set_trace_id(new_id: str | None = None) -> str:
    """手动设置当前的追踪 ID。"""
    trace_id = new_id or uuid.uuid4().hex
    trace_id_var.set(trace_id)
    return trace_id


@contextmanager
def trace_context(trace_id: str | None = None) -> Generator[str, None, None]:
    """追踪上下文管理器，离开时自动恢复。"""
    new_trace_id = trace_id or uuid.uuid4().hex
    token = trace_id_var.set(new_trace_id)
    try:
        yield new_trace_id
    finally:
        trace_id_var.reset(token)


def get_trace_id() -> str:
    """获取当前的追踪 ID。"""
    return trace_id_var.get()


def shutdown_logger() -> None:
    """优雅关闭日志，确保 enqueue 的日志已写盘。"""
    try:
        logger.complete()
    finally:
        logger.remove()


def add_custom_file(
    file_name: str,
    log_dir: Path | str = Path("logs"),
    level: str = "INFO",
    filter_rule: str | Callable[..., Any] | None = None,
) -> int:
    """运行时动态添加日志文件。"""
    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    return logger.add(
        target_dir / file_name,
        level=level,
        rotation="10 MB",
        filter=filter_rule,
    )
