import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from reborn_core.application import IdentitySnapshot, IdentitySnapshotStatus
from reborn_core.application.models import ModelMetadata, PromptMetadata
from reborn_core.infrastructure.database import (
    MigrationRunner,
    SQLiteDatabase,
    SQLiteIdentitySnapshotRepository,
    SQLiteSourceArtifactRepository,
    SQLiteTaskRepository,
)
from reborn_core.runtime import TaskStatus


class OpenAIStubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        payload = {
            "id": "chatcmpl-reflection-test",
            "object": "chat.completion",
            "created": 0,
            "model": "reflection-test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "worker-created reflection",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def _seed_active_snapshot(repository):
    content = "stable approved identity"
    repository.create_identity_snapshot(
        IdentitySnapshot(
            snapshot_id="approved-parent",
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            source_ids=("seed-source",),
            model=ModelMetadata("owner", "human-review"),
            prompt=PromptMetadata("identity", "1", "a" * 64),
            generation_params={},
            status=IdentitySnapshotStatus.APPROVED,
            active=True,
        )
    )


def test_cli_submission_is_completed_by_independent_worker_process(test_settings, tmp_path):
    database = SQLiteDatabase(app_settings=test_settings)
    MigrationRunner(database).migrate()
    snapshots = SQLiteIdentitySnapshotRepository(database)
    _seed_active_snapshot(snapshots)

    server = ThreadingHTTPServer(("127.0.0.1", 0), OpenAIStubHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    project_root = Path(__file__).parents[2]
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(test_settings.base_dir),
            "DB_PATH": str(test_settings.resolved_db_path),
            "PROJECT_PROFILE_PATH": str(test_settings.resolved_project_profile_path),
            "VECTOR_DB_PATH": str(test_settings.resolved_vector_db_path),
            "LOG_DIR": str(test_settings.resolved_log_dir),
            "LLM_API_KEY": "sk-local-reflection-test",
            "LLM_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
            "LLM_MODEL_NAME": "reflection-test-model",
            "PYTHONPATH": str(project_root / "src"),
        }
    )
    input_path = tmp_path / "reflection-input.json"
    private_text = "private CLI reflection source"
    input_path.write_text(
        json.dumps([{"role": "user", "content": private_text}]),
        encoding="utf-8",
    )

    submitted = subprocess.run(
        [
            sys.executable,
            "-m",
            "reborn_core",
            "nightly-reflection",
            str(input_path),
            "--confirm-authorized",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert submitted.returncode == 0, submitted.stderr
    submission = json.loads(submitted.stdout)
    task_id = submission["task_id"]
    artifact_id = submission["source_artifact_id"]

    task_repository = SQLiteTaskRepository(database)
    queued = task_repository.get_task(task_id)
    assert queued is not None
    assert queued.status is TaskStatus.QUEUED
    assert artifact_id in (queued.payload_json or "")
    assert private_text not in (queued.payload_json or "")

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
            task = task_repository.get_task(task_id)
            if task is not None and task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("Worker did not finish the nightly reflection task")
    finally:
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=10)

    task = task_repository.get_task(task_id)
    assert task is not None
    assert task.status is TaskStatus.SUCCEEDED, task.error

    artifact = SQLiteSourceArtifactRepository(database).get_source_artifact(artifact_id)
    assert artifact is not None
    assert artifact.metadata["parent_snapshot_id"] == "approved-parent"
    source_path = test_settings.base_dir / "data" / "memories" / artifact.storage_path
    assert source_path.is_file()

    candidates = snapshots.list_identity_snapshots(IdentitySnapshotStatus.PENDING_REVIEW)
    assert len(candidates) == 1
    assert candidates[0].source_ids == (artifact_id,)
    assert candidates[0].parent_snapshot_id == "approved-parent"
    assert candidates[0].content == "worker-created reflection"
