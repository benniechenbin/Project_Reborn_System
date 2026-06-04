"""已弃用的兼容导入；请改用 reborn_core.observability。"""

from reborn_core.observability import add_custom_file, logger, setup_logger, shutdown_logger

__all__ = ["add_custom_file", "logger", "setup_logger", "shutdown_logger"]
