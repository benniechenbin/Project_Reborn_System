import ast
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2] / "src" / "reborn_core"
LAYERS = {"application", "domains", "infrastructure", "interfaces"}
FORBIDDEN_IMPORTS = {
    "application": {"infrastructure", "interfaces"},
    "domains": {"application", "infrastructure", "interfaces"},
    "infrastructure": {"interfaces"},
}
ALLOWED_LEGACY_IMPORTS = {
    (
        "domains/brain/llm_router.py",
        "reborn_core.application.models",
    ),
    (
        "domains/brain/rag_engine.py",
        "reborn_core.application.ports",
    ),
    (
        "domains/memory/relational/db_manager.py",
        "reborn_core.application.models",
    ),
    (
        "domains/services/interview_service.py",
        "reborn_core.application.services.interview",
    ),
}


def _module_for_path(path: Path) -> str:
    parts = list(path.relative_to(SOURCE_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("reborn_core", *parts))


def _package_for_path(path: Path) -> str:
    module = _module_for_path(path)
    if path.name == "__init__.py":
        return module
    return module.rsplit(".", maxsplit=1)[0]


def _resolve_import_from(path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    package_parts = _package_for_path(path).split(".")
    base_parts = package_parts[: len(package_parts) - node.level + 1]
    if not base_parts:
        return node.module
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _imported_modules(path: Path) -> list[str]:
    modules: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_import_from(path, node)
            if module:
                modules.append(module)
    return modules


def _layer_for_module(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "reborn_core":
        return None
    return parts[1] if parts[1] in LAYERS else None


def _layer_for_path(path: Path) -> str | None:
    parts = path.relative_to(SOURCE_ROOT).parts
    return parts[0] if parts and parts[0] in LAYERS else None


def test_clean_architecture_import_boundaries_do_not_regress():
    violations = []
    for path in SOURCE_ROOT.rglob("*.py"):
        source_layer = _layer_for_path(path)
        if source_layer not in FORBIDDEN_IMPORTS:
            continue

        relative_path = path.relative_to(SOURCE_ROOT).as_posix()
        for module in _imported_modules(path):
            imported_layer = _layer_for_module(module)
            if imported_layer not in FORBIDDEN_IMPORTS[source_layer]:
                continue
            if (relative_path, module) in ALLOWED_LEGACY_IMPORTS:
                continue
            violations.append(f"{relative_path} imports {module}")

    assert violations == []
