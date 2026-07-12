import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from reborn_core.observability import logger

from .core import SQLiteDatabase

Migration = tuple[int, Callable[[sqlite3.Connection], None]]


class MigrationRunner:
    """Applies the project's versioned, forward-only SQLite migrations."""

    LATEST_VERSION = 4

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def migrate(self) -> None:
        """Apply every unapplied migration atomically in version order."""
        migrations: tuple[Migration, ...] = (
            (1, _migration_001_sync_history),
            (2, _migration_002_identity_snapshots),
            (3, _migration_003_background_tasks),
            (4, _migration_004_backup_and_audit),
        )
        with self.database.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                int(row["version"]) for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for version, migration in migrations:
                if version in applied:
                    continue
                migration(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )
        logger.info("SQLite migrations are current at version {}", self.LATEST_VERSION)


def _migration_001_sync_history(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_time TEXT NOT NULL,
            audio_duration REAL NOT NULL DEFAULT 0,
            notes_count INTEGER NOT NULL DEFAULT 0,
            word_count INTEGER NOT NULL DEFAULT 0,
            generation_id TEXT
        )
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(sync_history)")}
    if "generation_id" not in columns:
        conn.execute("ALTER TABLE sync_history ADD COLUMN generation_id TEXT")


def _migration_002_identity_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS identity_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            parent_snapshot_id TEXT,
            content TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            source_ids_json TEXT NOT NULL,
            model_provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_base_url TEXT,
            prompt_id TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            prompt_sha256 TEXT NOT NULL,
            generation_params_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT,
            review_note TEXT,
            active INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_identity_status ON identity_snapshots(status, created_at)"
    )


def _migration_003_background_tasks(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS background_tasks (
            task_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            result_json TEXT,
            error TEXT
        )
        """
    )


def _migration_004_backup_and_audit(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_records (
            backup_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            encrypted INTEGER NOT NULL,
            status TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            outcome TEXT NOT NULL,
            details_json TEXT NOT NULL
        )
        """
    )
