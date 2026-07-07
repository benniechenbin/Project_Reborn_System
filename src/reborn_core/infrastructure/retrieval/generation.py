import json
import os
import shutil
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from reborn_core.observability import logger


class GenerationVectorStore(Protocol):
    def add_documents(self, documents: list[Any]) -> None: ...

    def search(self, query: str, top_k: int = 5) -> list[Any]: ...


class NullMemoryRetriever:
    def search(self, query: str, top_k: int = 5) -> list[Any]:
        return []


class RetrievalGenerationManager:
    """构建相互隔离的索引，并原子切换活动代次指针。"""

    def __init__(
        self,
        root: Path,
        provider_factory: Callable[[Path], GenerationVectorStore],
        retention: int = 3,
    ) -> None:
        self.root = root
        self.generations_dir = root / "generations"
        self.pointer_path = root / "active_generation.json"
        self.provider_factory = provider_factory
        self.retention = max(retention, 2)
        self._lock = threading.RLock()
        self._active_store: GenerationVectorStore | None = None
        self._active_store_id: str | None = None

    def initialize(self) -> None:
        self.generations_dir.mkdir(parents=True, exist_ok=True)

    def build_and_activate(self, documents: list[Any]) -> str:
        if not documents:
            raise ValueError("Cannot build a retrieval generation without documents")
        with self._lock:
            self.initialize()
            generation_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:10]}"
            generation_dir = self.generations_dir / generation_id
            index_dir = generation_dir / "index"
            generation_dir.mkdir(parents=True, exist_ok=False)
            manifest = {
                "schema_version": 1,
                "generation_id": generation_id,
                "status": "building",
                "created_at": datetime.now(UTC).isoformat(),
                "document_count": len(documents),
                "error": None,
            }
            self._write_json_atomic(generation_dir / "manifest.json", manifest)

            try:
                store = self.provider_factory(index_dir)
                store.add_documents(documents)
                health_check = getattr(store, "health_check", None)
                if health_check is not None and not health_check():
                    raise RuntimeError("Retrieval generation health check failed")
                manifest["status"] = "ready"
                manifest["ready_at"] = datetime.now(UTC).isoformat()
                self._write_json_atomic(generation_dir / "manifest.json", manifest)
            except Exception as exc:
                manifest["status"] = "failed"
                manifest["error"] = str(exc)
                manifest["failed_at"] = datetime.now(UTC).isoformat()
                self._write_json_atomic(generation_dir / "manifest.json", manifest)
                logger.exception(
                    "Retrieval generation {} failed; active pointer unchanged", generation_id
                )
                raise

            self._write_json_atomic(
                self.pointer_path,
                {
                    "schema_version": 1,
                    "generation_id": generation_id,
                    "activated_at": datetime.now(UTC).isoformat(),
                },
            )
            self._active_store = store
            self._active_store_id = generation_id
            try:
                self._prune()
            except Exception:
                logger.exception("Generation pruning failed; active generation remains valid")
            logger.info("Activated retrieval generation {}", generation_id)
            return generation_id

    def active_generation_id(self) -> str | None:
        if not self.pointer_path.exists():
            return None
        try:
            payload = json.loads(self.pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read active retrieval generation pointer: {}", exc)
            return None
        if not isinstance(payload, dict):
            logger.warning("Active retrieval generation pointer is not a JSON object")
            return None
        generation_id = payload.get("generation_id")
        if not isinstance(generation_id, str) or not generation_id.strip():
            logger.warning("Active retrieval generation pointer has no valid generation_id")
            return None
        return generation_id

    def active_retriever(self) -> GenerationVectorStore | NullMemoryRetriever:
        with self._lock:
            generation_id = self.active_generation_id()
            if generation_id is None:
                return NullMemoryRetriever()
            if self._active_store is None or self._active_store_id != generation_id:
                self._active_store = self.provider_factory(
                    self._generation_path(generation_id) / "index"
                )
                self._active_store_id = generation_id
            return self._active_store

    def search(self, query: str, top_k: int = 5) -> list[Any]:
        return self.active_retriever().search(query, top_k)

    def rollback(self, generation_id: str) -> None:
        with self._lock:
            generation_dir = self._generation_path(generation_id)
            manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("status") != "ready":
                raise ValueError(f"Generation is not ready: {generation_id}")
            self._write_json_atomic(
                self.pointer_path,
                {
                    "schema_version": 1,
                    "generation_id": generation_id,
                    "activated_at": datetime.now(UTC).isoformat(),
                    "reason": "manual_rollback",
                },
            )
            self._active_store = None
            self._active_store_id = None

    def _prune(self) -> None:
        active = self.active_generation_id()
        ready: list[Path] = []
        for path in self.generations_dir.iterdir():
            manifest_path = path / "manifest.json"
            if not path.is_dir() or not manifest_path.exists() or path.name == active:
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("status") == "ready":
                ready.append(path)
        ready.sort(key=lambda path: path.name, reverse=True)
        for path in ready[self.retention - 1 :]:
            resolved = path.resolve()
            if self.generations_dir.resolve() not in resolved.parents:
                raise RuntimeError(f"Refusing to prune path outside generation root: {resolved}")
            shutil.rmtree(resolved)

    def _generation_path(self, generation_id: str) -> Path:
        path = (self.generations_dir / generation_id).resolve()
        if self.generations_dir.resolve() not in path.parents:
            raise ValueError("Invalid retrieval generation ID")
        if not path.exists():
            raise LookupError(f"Retrieval generation not found: {generation_id}")
        return path

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
