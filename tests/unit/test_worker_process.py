import os
import subprocess
import sys
import time
from pathlib import Path

from reborn_core.infrastructure.backup import BackupService
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteBackupRecordRepository,
    SQLiteDatabase,
    SQLiteTaskRepository,
)
from reborn_core.runtime import TaskQueue, TaskStatus
from reborn_core.security import LocalOwnerAccessPolicy


def test_worker_cli_process_executes_ten_persisted_tasks(test_settings):
    settings = test_settings.model_copy(update={"backup_require_encryption": False})
    database = SQLiteDatabase(app_settings=settings)
    MigrationRunner(database).migrate()
    backup_service = BackupService(
        settings,
        SQLiteBackupRecordRepository(database),
        LocalOwnerAccessPolicy(),
    )
    source_backup = backup_service.create_backup()
    repository = SQLiteTaskRepository(database)
    queue = TaskQueue(repository)
    task_ids = [
        queue.submit("recovery_drill", source_backup, allow_parallel=True) for _ in range(10)
    ]

    project_root = Path(__file__).parents[2]
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(settings.base_dir),
            "DB_PATH": str(settings.resolved_db_path),
            "BACKUP_DIR": str(settings.resolved_backup_dir),
            "BACKUP_REQUIRE_ENCRYPTION": "false",
            "PROJECT_PROFILE_PATH": str(settings.resolved_project_profile_path),
            "VECTOR_DB_PATH": str(settings.resolved_vector_db_path),
            "LOG_DIR": str(settings.resolved_log_dir),
            "PYTHONPATH": str(project_root / "src"),
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "reborn_core", "worker"],
        cwd=project_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            tasks = [repository.get_task(task_id) for task_id in task_ids]
            if all(task is not None and task.status is TaskStatus.SUCCEEDED for task in tasks):
                break
            time.sleep(0.1)
        else:
            statuses = [
                repository.get_task(task_id).status if repository.get_task(task_id) else None
                for task_id in task_ids
            ]
            raise AssertionError(f"Worker did not complete all tasks: {statuses}")
    finally:
        process.terminate()
        process.wait(timeout=10)

    assert all(
        repository.get_task(task_id).status is TaskStatus.SUCCEEDED
        for task_id in task_ids
        if repository.get_task(task_id) is not None
    )
