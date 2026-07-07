import hashlib
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from reborn_core.observability import logger


class ManagedRebornApp(Protocol):
    @property
    def started(self) -> bool: ...

    def shutdown(self) -> None: ...


AppT = TypeVar("AppT", bound=ManagedRebornApp)


@dataclass
class CachedRebornApp(Generic[AppT]):
    """Wraps a RebornApp cached by Streamlit so stale resources can be closed."""

    app: AppT
    token: str
    _closed: bool = False

    def is_valid(self, token: str) -> bool:
        return not self._closed and self.app.started and self.token == token

    def shutdown(self) -> None:
        if self._closed:
            return
        self.app.shutdown()
        self._closed = True

    def __del__(self) -> None:
        try:
            self.shutdown()
        except Exception as exc:
            logger.warning(
                "Could not close cached Streamlit RebornApp during finalization: {}", exc
            )


_active_lock = threading.Lock()
_active_cached_app_ref: weakref.ReferenceType[CachedRebornApp[Any]] | None = None


def register_cached_app(cached_app: CachedRebornApp[AppT]) -> CachedRebornApp[AppT]:
    """Registers a newly cached app and closes any previous active wrapper."""
    global _active_cached_app_ref

    with _active_lock:
        previous = _active_cached_app_ref() if _active_cached_app_ref is not None else None
        if previous is not None and previous is not cached_app:
            try:
                previous.shutdown()
            except Exception as exc:
                logger.warning("Could not close previous cached Streamlit RebornApp: {}", exc)
        _active_cached_app_ref = weakref.ref(cached_app)
    return cached_app


def is_cached_app_valid(
    cached_app: CachedRebornApp[Any],
    token_factory: Callable[[], str] | None = None,
) -> bool:
    """Validation callback for st.cache_resource."""
    token_factory = token_factory or streamlit_cache_token
    if cached_app.is_valid(token_factory()):
        return True
    cached_app.shutdown()
    return False


def streamlit_cache_token(project_root: Path | None = None) -> str:
    """Builds a lightweight source fingerprint for Streamlit resource validation."""
    root = project_root or _project_root()
    source_root = root / "src" / "reborn_core"
    candidates = [root / "app.py"]
    if source_root.exists():
        candidates.extend(sorted(source_root.rglob("*.py")))

    digest = hashlib.sha256()
    for path in candidates:
        try:
            stat = path.stat()
        except OSError as exc:
            logger.warning("Could not stat Streamlit cache source {}: {}", path, exc)
            continue
        digest.update(_relative_source_name(path, root).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b":")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _relative_source_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
