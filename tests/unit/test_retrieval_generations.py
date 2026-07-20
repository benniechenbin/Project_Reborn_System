import json
import multiprocessing

import pytest

from reborn_core.core.exceptions import ConcurrencyConflictError
from reborn_core.infrastructure.retrieval import RetrievalGenerationManager


class FakeStore:
    def __init__(self, path, fail=False):
        self.path = path
        self.fail = fail
        self.documents = []

    def add_documents(self, documents):
        if self.fail:
            raise RuntimeError("build failed")
        self.path.mkdir(parents=True, exist_ok=True)
        self.documents = documents

    def health_check(self):
        return bool(self.documents)

    def search(self, query, top_k=5):
        return self.documents[:top_k]


class BlockingStore(FakeStore):
    def __init__(self, path, entered, release):
        super().__init__(path)
        self.entered = entered
        self.release = release

    def add_documents(self, documents):
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("test did not release the blocking generation build")
        super().add_documents(documents)


def _build_generation_in_child(root, entered, release, results):
    manager = RetrievalGenerationManager(
        root,
        lambda path: BlockingStore(path, entered, release),
    )
    try:
        generation_id = manager.build_and_activate(["child-process"])
    except Exception as exc:
        results.put(("error", type(exc).__name__, str(exc)))
        raise
    results.put(("ok", generation_id))


def test_generation_failure_leaves_active_pointer_unchanged(tmp_path):
    fail = False

    def factory(path):
        return FakeStore(path, fail=fail)

    manager = RetrievalGenerationManager(tmp_path, factory)
    first = manager.build_and_activate(["v1"])
    fail = True

    with pytest.raises(RuntimeError, match="build failed"):
        manager.build_and_activate(["v2"])

    assert manager.active_generation_id() == first
    assert manager.search("anything") == ["v1"]

    fail = False
    recovered = manager.build_and_activate(["v3"])

    assert manager.active_generation_id() == recovered
    assert not manager.lease_path.exists()


def test_generation_can_rollback_to_previous_ready_index(tmp_path):
    manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path), retention=3)
    first = manager.build_and_activate(["v1"])
    second = manager.build_and_activate(["v2"])

    assert manager.active_generation_id() == second
    manager.rollback(first)
    assert manager.active_generation_id() == first


def test_prune_failure_does_not_invalidate_activated_generation(tmp_path, monkeypatch):
    manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path), retention=2)
    first = manager.build_and_activate(["v1"])
    monkeypatch.setattr(manager, "_prune", lambda: (_ for _ in ()).throw(OSError("locked")))

    second = manager.build_and_activate(["v2"])

    assert second != first
    assert manager.active_generation_id() == second
    assert manager.search("anything") == ["v2"]


def test_each_generation_uses_an_isolated_index_path(tmp_path):
    index_paths = []

    def factory(path):
        index_paths.append(path)
        return FakeStore(path)

    manager = RetrievalGenerationManager(tmp_path, factory, retention=3)
    manager.build_and_activate(["v1"])
    manager.build_and_activate(["v2"])

    assert len(index_paths) == 2
    assert index_paths[0] != index_paths[1]
    assert all(path.name == "index" for path in index_paths)


def test_corrupt_active_generation_pointer_falls_back_to_null_retriever(tmp_path):
    manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path), retention=3)
    manager.initialize()
    manager.pointer_path.write_text("{not valid json", encoding="utf-8")

    assert manager.active_generation_id() is None
    assert manager.search("anything") == []


def test_invalid_active_generation_pointer_shape_is_ignored(tmp_path):
    manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path), retention=3)
    manager.initialize()
    manager.pointer_path.write_text('{"schema_version": 1}', encoding="utf-8")

    assert manager.active_generation_id() is None
    assert manager.search("anything") == []


def test_cross_process_writer_conflict_fails_fast_and_preserves_single_generation(tmp_path):
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    results = context.Queue()
    process = context.Process(
        target=_build_generation_in_child,
        args=(tmp_path, entered, release, results),
    )
    process.start()

    try:
        assert entered.wait(timeout=10)
        manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path))
        lease = json.loads(manager.lease_path.read_text(encoding="utf-8"))

        assert lease["operation"] == "build_and_activate"
        assert lease["pid"] == process.pid
        with pytest.raises(ConcurrencyConflictError, match="already running"):
            manager.build_and_activate(["parent-process"])
    finally:
        release.set()
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert process.exitcode == 0
    status, generation_id = results.get(timeout=5)
    assert status == "ok"
    manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path))
    assert manager.active_generation_id() == generation_id
    assert len(list(manager.generations_dir.iterdir())) == 1
    assert not manager.lease_path.exists()


def test_rollback_rejects_concurrent_generation_build(tmp_path):
    manager = RetrievalGenerationManager(tmp_path, lambda path: FakeStore(path))
    first = manager.build_and_activate(["v1"])
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    results = context.Queue()
    process = context.Process(
        target=_build_generation_in_child,
        args=(tmp_path, entered, release, results),
    )
    process.start()

    try:
        assert entered.wait(timeout=10)
        with pytest.raises(ConcurrencyConflictError, match="already running"):
            manager.rollback(first)
        assert manager.active_generation_id() == first
    finally:
        release.set()
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert process.exitcode == 0
    assert results.get(timeout=5)[0] == "ok"
