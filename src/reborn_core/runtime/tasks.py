import base64
import json
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Protocol

from reborn_core.core.exceptions import RebornError
from reborn_core.observability import logger

PAYLOAD_SCHEMA_VERSION = 1
TYPE_MARKER = "__reborn_type__"


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
    payload_json: str | None = None
    result_json: str | None = None
    error: str | None = None


class TaskRepository(Protocol):
    def enqueue_task(self, task: TaskRecord) -> None: ...

    def claim_next_queued_task(self) -> TaskRecord | None: ...

    def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result_json: str | None = None,
        error: str | None = None,
    ) -> None: ...

    def get_task(self, task_id: str) -> TaskRecord | None: ...

    def has_active_task_of_kind(self, kind: str) -> bool: ...

    def recover_interrupted_tasks(self) -> int: ...


TaskHandler = Callable[..., Any]


class BackgroundTaskRunner:
    """SQLite-backed polling worker with explicit, restart-safe lifecycle."""

    def __init__(
        self,
        repository: TaskRepository,
        handlers: Mapping[str, TaskHandler] | None = None,
        max_workers: int = 2,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self.repository = repository
        self.handlers = dict(handlers or {})
        self.max_workers = max_workers
        self.poll_interval_seconds = poll_interval_seconds
        self._executor: ThreadPoolExecutor | None = None
        self._dispatcher: threading.Thread | None = None
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

    @property
    def started(self) -> bool:
        with self._lock:
            return self._dispatcher is not None

    def start(self) -> None:
        with self._lock:
            if self._dispatcher is not None:
                return
            self._stop_event.clear()
            self._wake_event.clear()
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="reborn-worker",
            )
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop,
                name="reborn-task-dispatcher",
                daemon=True,
            )
            dispatcher = self._dispatcher
        dispatcher.start()

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            dispatcher = self._dispatcher
            executor = self._executor
            self._dispatcher = None
            self._executor = None
        self._stop_event.set()
        self._wake_event.set()
        if dispatcher is not None:
            dispatcher.join()
        if executor is not None:
            executor.shutdown(wait=wait, cancel_futures=False)
        with self._lock:
            self._futures.clear()

    def submit(self, kind: str, *args: Any, **kwargs: Any) -> str:
        task_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()
        self.repository.enqueue_task(
            TaskRecord(
                task_id=task_id,
                kind=kind,
                status=TaskStatus.QUEUED,
                created_at=now,
                updated_at=now,
                payload_json=_encode_payload(args, kwargs),
            )
        )
        self._wake_event.set()
        return task_id

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.repository.get_task(task_id)

    def result(self, task_id: str) -> Any:
        while True:
            task = self.repository.get_task(task_id)
            if task is None:
                raise LookupError(f"Task result is not available: {task_id}")
            if task.status is TaskStatus.FAILED:
                detail = f": {task.error}" if task.error else ""
                raise RuntimeError(f"Task failed{detail}")
            if task.status is TaskStatus.SUCCEEDED:
                if task.result_json is None:
                    return None
                try:
                    return json.loads(task.result_json)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Stored task result is not valid JSON: {task_id}") from exc
            if not self.started:
                raise LookupError(f"Task is queued but the runner is not started: {task_id}")
            time.sleep(min(self.poll_interval_seconds, 0.05))

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            dispatched = False
            while not self._stop_event.is_set() and self._available_worker_slots() > 0:
                task = self.repository.claim_next_queued_task()
                if task is None:
                    break
                dispatched = True
                self._dispatch(task)
            if dispatched:
                continue
            self._wake_event.wait(self.poll_interval_seconds)
            self._wake_event.clear()

    def _available_worker_slots(self) -> int:
        with self._lock:
            return max(0, self.max_workers - len(self._futures))

    def _dispatch(self, task: TaskRecord) -> None:
        handler = self.handlers.get(task.kind)
        if handler is None:
            self.repository.update_task(
                task.task_id,
                TaskStatus.FAILED,
                error=f"No task handler is registered for kind '{task.kind}'",
            )
            return
        try:
            args, kwargs = _decode_payload(task.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.repository.update_task(
                task.task_id,
                TaskStatus.FAILED,
                error=f"Task payload cannot be replayed: {exc}",
            )
            return

        with self._lock:
            executor = self._executor
            if executor is None:
                self.repository.update_task(
                    task.task_id,
                    TaskStatus.FAILED,
                    error="Task runner stopped before dispatch",
                )
                return
            future = executor.submit(self._run, task.task_id, handler, args, kwargs)
            self._futures[task.task_id] = future

        def discard_completed_future(completed: Future[Any]) -> None:
            self._discard_future(task.task_id, completed)

        future.add_done_callback(discard_completed_future)

    def _discard_future(self, task_id: str, future: Future[Any]) -> None:
        with self._lock:
            if self._futures.get(task_id) is future:
                self._futures.pop(task_id, None)
        self._wake_event.set()

    def _run(
        self,
        task_id: str,
        operation: TaskHandler,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        try:
            result = operation(*args, **kwargs)
            self.repository.update_task(
                task_id,
                TaskStatus.SUCCEEDED,
                result_json=json.dumps(_jsonable(result), ensure_ascii=False),
            )
            return result
        except RebornError as exc:
            logger.error("Background task {} failed: {}", task_id, exc)
            self.repository.update_task(task_id, TaskStatus.FAILED, error=str(exc))
            return None
        except Exception as exc:
            logger.exception("Background task {} failed", task_id)
            self.repository.update_task(task_id, TaskStatus.FAILED, error=str(exc))
            return None


def _encode_payload(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "schema_version": PAYLOAD_SCHEMA_VERSION,
            "args": _payload_value(args),
            "kwargs": _payload_value(kwargs),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode_payload(payload_json: str | None) -> tuple[tuple[Any, ...], dict[str, Any]]:
    if payload_json is None:
        raise ValueError("payload is missing; the task predates persistent payloads")
    payload = json.loads(payload_json)
    if not isinstance(payload, dict) or payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
        raise ValueError("unsupported payload schema version")
    args = _restore_payload_value(payload.get("args"))
    kwargs = _restore_payload_value(payload.get("kwargs"))
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        raise TypeError("payload args or kwargs have an invalid shape")
    return tuple(args), kwargs


def _payload_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {TYPE_MARKER: "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Path):
        return {TYPE_MARKER: "path", "value": str(value)}
    if isinstance(value, Enum):
        return _payload_value(value.value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("task payload mappings must use string keys")
        return {key: _payload_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_payload_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported task payload type: {type(value).__name__}")


def _restore_payload_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_restore_payload_value(item) for item in value]
    if isinstance(value, dict):
        marker = value.get(TYPE_MARKER)
        if marker == "bytes" and set(value) == {TYPE_MARKER, "base64"}:
            try:
                return base64.b64decode(value["base64"], validate=True)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid base64 bytes payload") from exc
        if marker == "path" and set(value) == {TYPE_MARKER, "value"}:
            if not isinstance(value["value"], str):
                raise TypeError("path payload value must be a string")
            return Path(value["value"])
        if marker is not None:
            raise ValueError(f"unsupported task payload marker: {marker}")
        return {str(key): _restore_payload_value(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported decoded payload type: {type(value).__name__}")


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
