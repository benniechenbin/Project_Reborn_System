import json
import threading
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Protocol

from reborn_core.observability import logger


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    kind: str
    status: TaskStatus
    created_at: str
    updated_at: str
    result_json: str | None = None
    error: str | None = None


class TaskRepository(Protocol):
    def create_task(self, task: TaskRecord) -> None: ...

    def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result_json: str | None = None,
        error: str | None = None,
    ) -> None: ...

    def get_task(self, task_id: str) -> TaskRecord | None: ...


class BackgroundTaskRunner:
    """具有持久化状态记录和显式生命周期的进程内工作器。"""

    def __init__(self, repository: TaskRepository, max_workers: int = 2) -> None:
        self.repository = repository
        self.max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="reborn-worker",
                )

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=wait, cancel_futures=False)

    def submit(self, kind: str, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        self.start()
        task_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()
        self.repository.create_task(
            TaskRecord(
                task_id=task_id,
                kind=kind,
                status=TaskStatus.QUEUED,
                created_at=now,
                updated_at=now,
            )
        )
        assert self._executor is not None
        future = self._executor.submit(self._run, task_id, operation, args, kwargs)
        with self._lock:
            self._futures[task_id] = future
        return task_id

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.repository.get_task(task_id)

    def result(self, task_id: str) -> Any:
        with self._lock:
            future = self._futures.get(task_id)
        if future is None:
            raise LookupError(f"Task result is not available in this process: {task_id}")
        return future.result()

    def _run(
        self,
        task_id: str,
        operation: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        self.repository.update_task(task_id, TaskStatus.RUNNING)
        try:
            result = operation(*args, **kwargs)
            self.repository.update_task(
                task_id,
                TaskStatus.SUCCEEDED,
                result_json=json.dumps(_jsonable(result), ensure_ascii=False),
            )
            return result
        except Exception as exc:
            logger.exception("Background task {} failed", task_id)
            self.repository.update_task(task_id, TaskStatus.FAILED, error=str(exc))
            raise


def _jsonable(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return _jsonable(value.as_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
