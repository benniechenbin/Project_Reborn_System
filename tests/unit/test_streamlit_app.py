import ast
from pathlib import Path

from reborn_core.interfaces.streamlit import app as streamlit_app


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
