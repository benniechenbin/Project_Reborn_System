import pytest

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
