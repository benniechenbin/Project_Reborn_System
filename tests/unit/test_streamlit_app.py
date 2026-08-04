import ast
from pathlib import Path

from reborn_core.interfaces.streamlit import app as streamlit_app


class FakeStreamlit:
    def __init__(self, session_state):
        self.session_state = session_state
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


def test_streamlit_interface_exports_main_without_starting_lifecycle():
    assert callable(streamlit_app.main)
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]

    assert top_level_calls == []


def test_root_app_is_only_a_compatibility_launcher():
    root_app = Path(__file__).parents[2] / "app.py"
    tree = ast.parse(root_app.read_text(encoding="utf-8"))
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]

    assert len(imports) == 1
    imported = imports[0]
    assert isinstance(imported, ast.ImportFrom)
    assert imported.module == "reborn_core.interfaces.streamlit.app"
    assert [alias.name for alias in imported.names] == ["main"]


def test_streamlit_task_submissions_do_not_persist_bound_methods():
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")

    assert "container.run_interview," not in source
    assert "container.process_voice_capture," not in source
    assert "container.generate_avatar_response," not in source
    assert "container.run_recovery_drill," not in source


def test_streamlit_uses_native_audio_inputs_and_never_starts_worker():
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")

    assert "audio_recorder_streamlit" not in source
    assert "container.task_runner" not in source
    assert "container.task_worker" not in source
    assert "st.audio_input(" in source
    assert "sample_rate=48000" in source
    assert "sample_rate=16000" in source
    assert '"声音档案"' in source
    assert "container.voice_archive_service.archive(" in source


def test_submit_task_preserves_existing_task_and_warns_on_duplicate(monkeypatch):
    class DuplicateQueue:
        def submit(self, kind, *args):
            raise ValueError(f"A background task of kind '{kind}' is already running")

    fake_st = FakeStreamlit({"sync_task": "existing-task"})
    container = type("FakeContainer", (), {"task_queue": DuplicateQueue()})()
    monkeypatch.setattr(streamlit_app, "st", fake_st)

    assert streamlit_app.submit_task(container, "sync_task", "memory_sync") is False
    assert fake_st.session_state["sync_task"] == "existing-task"
    assert fake_st.warnings == [
        "Task was not submitted again: A background task of kind 'memory_sync' is already running"
    ]


def test_submit_task_stores_new_task_after_success(monkeypatch):
    class SuccessfulQueue:
        def submit(self, kind, *args):
            return "new-task"

    fake_st = FakeStreamlit({})
    container = type("FakeContainer", (), {"task_queue": SuccessfulQueue()})()
    monkeypatch.setattr(streamlit_app, "st", fake_st)

    assert streamlit_app.submit_task(container, "sync_task", "memory_sync") is True
    assert fake_st.session_state["sync_task"] == "new-task"
    assert fake_st.warnings == []
