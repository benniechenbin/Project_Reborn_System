import errno
import importlib
import json
import os
import socket
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Any

from reborn_core.core.exceptions import ConcurrencyConflictError, InfrastructureError
from reborn_core.observability import logger


class CrossProcessFileLease:
    """Owns a non-blocking OS file lock for the lifetime of a context manager."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.lock_path = root / ".generation-write.lock"
        self.metadata_path = root / "generation_write_lease.json"

    @contextmanager
    def acquire(self, operation: str) -> Iterator[dict[str, str | int]]:
        """Acquire the write lease or fail immediately when another process owns it."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InfrastructureError(
                f"Could not create retrieval generation lock directory: {exc}"
            ) from exc
        handle = self._open_lock_file()
        try:
            self._prepare_lock_file(handle)
            try:
                _lock_nonblocking(handle)
            except OSError as exc:
                if _is_lock_contention(exc):
                    holder = self._read_metadata()
                    raise ConcurrencyConflictError(self._conflict_message(holder)) from exc
                raise InfrastructureError(
                    f"Could not acquire retrieval generation write lease: {exc}"
                ) from exc

            metadata: dict[str, str | int] = {
                "lease_id": uuid.uuid4().hex,
                "operation": operation,
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "acquired_at": datetime.now(UTC).isoformat(),
            }
            try:
                self._write_metadata_atomic(metadata)
            except OSError as exc:
                _unlock(handle)
                raise InfrastructureError(
                    f"Could not write retrieval generation lease metadata: {exc}"
                ) from exc

            try:
                yield metadata
            finally:
                try:
                    self._remove_owned_metadata(str(metadata["lease_id"]))
                finally:
                    _unlock(handle)
        finally:
            handle.close()

    def _open_lock_file(self) -> BinaryIO:
        try:
            return self.lock_path.open("a+b")
        except OSError as exc:
            raise InfrastructureError(
                f"Could not open retrieval generation lock file: {exc}"
            ) from exc

    @staticmethod
    def _prepare_lock_file(handle: BinaryIO) -> None:
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
        except OSError as exc:
            raise InfrastructureError(
                f"Could not prepare retrieval generation lock file: {exc}"
            ) from exc

    def _read_metadata(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read retrieval generation lease metadata: {}", exc)
            return None
        return payload if isinstance(payload, dict) else None

    def _write_metadata_atomic(self, metadata: dict[str, str | int]) -> None:
        temp_path = self.metadata_path.with_name(
            f".{self.metadata_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, self.metadata_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _remove_owned_metadata(self, lease_id: str) -> None:
        metadata = self._read_metadata()
        if metadata is None or metadata.get("lease_id") != lease_id:
            return
        try:
            self.metadata_path.unlink(missing_ok=True)
        except OSError as exc:
            raise InfrastructureError(
                f"Could not remove retrieval generation lease metadata: {exc}"
            ) from exc

    @staticmethod
    def _conflict_message(holder: dict[str, Any] | None) -> str:
        if holder is None:
            return "A retrieval generation write operation is already running"
        operation = holder.get("operation", "unknown")
        pid = holder.get("pid", "unknown")
        hostname = holder.get("hostname", "unknown")
        acquired_at = holder.get("acquired_at", "unknown")
        return (
            "A retrieval generation write operation is already running "
            f"(operation={operation}, pid={pid}, host={hostname}, acquired_at={acquired_at})"
        )


def _lock_nonblocking(handle: BinaryIO) -> None:
    if os.name == "nt":
        msvcrt: Any = importlib.import_module("msvcrt")

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: BinaryIO) -> None:
    try:
        if os.name == "nt":
            msvcrt: Any = importlib.import_module("msvcrt")

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise InfrastructureError(
            f"Could not release retrieval generation write lease: {exc}"
        ) from exc


def _is_lock_contention(exc: OSError) -> bool:
    return exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(
        exc, "winerror", None
    ) in {33, 36}
