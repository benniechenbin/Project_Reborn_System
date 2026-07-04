from pathlib import Path


def test_production_code_does_not_use_assert_statements():
    source_root = Path(__file__).parents[2] / "src" / "reborn_core"
    offenders = []
    for path in source_root.rglob("*.py"):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("assert "):
                offenders.append(f"{path.relative_to(source_root)}:{line_number}")

    assert offenders == []
