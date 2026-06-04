import re


def parse_frontmatter(content: str) -> dict[str, str | list[str]]:
    """提取摄入流水线需要使用的少量元数据。"""
    metadata: dict[str, str | list[str]] = {
        "date": "未知日期",
        "tags": [],
        "source": "upload",
    }
    yaml_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not yaml_match:
        return metadata

    yaml_text = yaml_match.group(1)
    date_match = re.search(
        r'^date:\s*["\']?(\d{4}[-/]\d{2}[-/]\d{2})["\']?',
        yaml_text,
        re.MULTILINE,
    )
    if date_match:
        metadata["date"] = date_match.group(1).replace("/", "-")

    tags_match = re.search(r"^tags:\s*(.*)", yaml_text, re.MULTILINE)
    if tags_match:
        raw_tags = (
            tags_match.group(1)
            .strip()
            .replace("[", "")
            .replace("]", "")
            .replace('"', "")
            .replace("'", "")
        )
        metadata["tags"] = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    return metadata
