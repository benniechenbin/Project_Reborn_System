import sys
from pathlib import Path


def main() -> None:
    env_file = Path(".env")
    example_file = Path(".env.example")
    if not env_file.exists():
        return
    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    example_lines: list[str] = []
    for line in lines:
        original_line = line.rstrip("\n")
        stripped_line = original_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            example_lines.append(original_line)
        elif "=" in original_line:
            key_part, val_part = original_line.split("=", 1)
            if "#" in val_part:
                comment_idx = val_part.find("#")
                comment = val_part[comment_idx:]
                example_lines.append(f"{key_part}={comment}")
            else:
                example_lines.append(f"{key_part}=")
        else:
            example_lines.append(original_line)
    new_content = "\n".join(example_lines) + "\n"
    if example_file.exists():
        with open(example_file, "r", encoding="utf-8") as f:
            if f.read() == new_content:
                return
    with open(example_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("✅ 成功从 .env 生成脱敏的 .env.example 文件！")
    print("⚠️ 请将更新后的 .env.example 添加到暂存区 (git add) 并重新提交。")
    sys.exit(1)


if __name__ == "__main__":
    main()
