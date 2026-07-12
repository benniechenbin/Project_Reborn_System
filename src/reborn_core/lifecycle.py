import atexit
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections.abc import Generator

from reborn_core.config import Settings
from reborn_core.container import Container
from reborn_core.core.banner import show_banner
from reborn_core.observability import logger, setup_logger, shutdown_logger


@dataclass(slots=True)
class RebornApp:
    """统一管理进程启动与关闭期间产生的副作用。"""

    settings: Settings
    container: Container
    _started: bool = field(default=False, init=False, repr=False)
    _atexit_registered: bool = field(default=False, init=False, repr=False)

    @property
    def started(self) -> bool:
        return self._started

    def start(self, show_startup_banner: bool = True) -> "RebornApp":
        if self._started:
            return self
        if show_startup_banner:
            show_banner(text=self.settings.app_name, font="slant")
        setup_logger(
            log_dir=self.settings.resolved_log_dir,
            log_level=self.settings.log_level,
            log_format=self.settings.log_format,
            app_env=self.settings.app_env,
        )
        for path in (
            self.settings.resolved_log_dir,
            self.settings.resolved_models_dir,
            self.settings.resolved_db_path.parent,
            self.settings.resolved_vector_db_path,
            self.settings.resolved_backup_dir,
            self.settings.resolved_legacy_activation_file.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

        self.container.migration_runner.migrate()
        abandoned_tasks = self.container.task_repository.mark_unfinished_tasks_failed()
        self.container.retrieval_generations.initialize()
        self.container.task_runner.start()
        self._started = True
        if not self._atexit_registered:
            atexit.register(self.shutdown)
            self._atexit_registered = True
        logger.info(
            "{} {} started; retrieval generation={}",
            self.settings.app_name,
            self.settings.app_version,
            self.container.retrieval_generations.active_generation_id(),
        )
        if abandoned_tasks:
            logger.warning("Marked {} interrupted background tasks as failed", abandoned_tasks)
        return self

    def shutdown(self) -> None:
        if not self._started:
            return
        self.container.task_runner.shutdown(wait=True)
        logger.info("{} stopped", self.settings.app_name)
        shutdown_logger()
        if self._atexit_registered:
            try:
                atexit.unregister(self.shutdown)
            except Exception:
                pass
            self._atexit_registered = False
        self._started = False


def build_app(app_settings: Settings | None = None) -> RebornApp:
    settings = app_settings or Settings()
    return RebornApp(settings=settings, container=Container(app_settings=settings))


@contextmanager
def lifespan(
    app_settings: Settings | None = None,
    show_startup_banner: bool = True,
) -> Generator[RebornApp, None, None]:
    app = build_app(app_settings).start(show_startup_banner=show_startup_banner)
    try:
        yield app
    finally:
        app.shutdown()
