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
        # 仅去掉行尾换行符，保留原有的空格排版
        original_line = line.rstrip("\n")
        stripped_line = original_line.strip()

        # 保留空行和整行注释
        if not stripped_line or stripped_line.startswith("#"):
            example_lines.append(original_line)
        elif "=" in original_line:
            key_part, val_part = original_line.split("=", 1)

            # 进阶优化：尝试保留行内注释 (例如: KEY=VALUE # comment)
            # 注意：这只是一个轻量级实现，不处理带有 "#" 的复杂字符串值
            if "#" in val_part:
                comment_idx = val_part.find("#")
                comment = val_part[comment_idx:]
                example_lines.append(f"{key_part}={comment}")
            else:
                example_lines.append(f"{key_part}=")
        else:
            example_lines.append(original_line)

    new_content = "\n".join(example_lines) + "\n"

    # 核心优化：如果内容没有发生变化，直接退出，不执行写入操作（拦截通过）
    if example_file.exists():
        with open(example_file, "r", encoding="utf-8") as f:
            if f.read() == new_content:
                return

    # 只有当内容确实改变（或文件不存在）时才写入
    with open(example_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("✅ 成功从 .env 生成脱敏的 .env.example 文件！")
    print("⚠️ 请将更新后的 .env.example 添加到暂存区 (git add) 并重新提交。")

    sys.exit(1)


if __name__ == "__main__":
    main()
