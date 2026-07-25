from __future__ import annotations

import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, get_args

from pydantic import SecretBytes, SecretStr
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from reborn_core.config import Settings

DEFAULT_OUTPUT_FILE = PROJECT_ROOT / ".env.example"
EXCLUDED_FIELDS = {"base_dir"}


def _annotation_contains_secret(annotation: Any) -> bool:
    if annotation in {SecretStr, SecretBytes}:
        return True
    return any(_annotation_contains_secret(arg) for arg in get_args(annotation))


def _default_to_env_value(field: FieldInfo) -> str:
    if _annotation_contains_secret(field.annotation):
        return ""

    value = field.default
    if value is PydanticUndefined or value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_env_example(settings_class: type[Settings] = Settings) -> str:
    lines = [
        "# 根据 reborn_core.config.Settings 自动生成。",
        "# 真实凭证只能保存在 .env 中。",
        "",
    ]
    for field_name, field in settings_class.model_fields.items():
        if field_name in EXCLUDED_FIELDS:
            continue
        if field.description:
            lines.append(f"# {field.description}")
        lines.append(f"{field_name.upper()}={_default_to_env_value(field)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_env_example(output_file: Path = DEFAULT_OUTPUT_FILE) -> bool:
    content = build_env_example()
    if output_file.exists() and output_file.read_text(encoding="utf-8") == content:
        return False
    output_file.write_text(content, encoding="utf-8")
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据 Settings 生成 .env.example。")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    expected = build_env_example()
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current == expected:
            return 0
        print(f"{args.output} 已过期。", file=sys.stderr)
        return 1

    print(f"已更新 {args.output}" if write_env_example(args.output) else f"{args.output} 已是最新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
