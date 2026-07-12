import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Literal

from reborn_core.config import Settings


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that always closes when leaving a context manager."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()
        return False


class SQLiteDatabase:
    """Owns SQLite connection and transaction policy for repository adapters."""

    def __init__(
        self,
        app_settings: Settings | None = None,
        db_path: Path | None = None,
    ) -> None:
        if db_path is not None:
            self.db_path = db_path
        elif app_settings is not None:
            self.db_path = app_settings.resolved_db_path
        else:
            raise ValueError("app_settings must be provided if db_path is not specified")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create a configured, short-lived SQLite connection."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30,
            factory=ClosingConnection,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Run statements in an immediate transaction with explicit rollback."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
