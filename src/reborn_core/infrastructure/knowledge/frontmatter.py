import re
import yaml


def parse_frontmatter(content: str) -> dict[str, str | list[str]]:
    """提取摄入流水线需要使用的少量元数据。"""
    metadata: dict[str, str | list[str]] = {
        "date": "未知日期",
        "tags": [],
        "source": "upload",
    }
    yaml_match = re.search(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not yaml_match:
        return metadata

    try:
        data = yaml.safe_load(yaml_match.group(1))
        if not isinstance(data, dict):
            return metadata

        # 处理 date
        if "date" in data:
            date_val = data["date"]
            if isinstance(date_val, (str, int)):
                date_str = str(date_val).replace("/", "-")
                if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
                    metadata["date"] = date_str[:10]
            elif hasattr(date_val, "strftime"):  # datetime.date / datetime.datetime
                metadata["date"] = date_val.strftime("%Y-%m-%d")

        # 处理 tags
        if "tags" in data:
            tags_val = data["tags"]
            if isinstance(tags_val, list):
                metadata["tags"] = [str(t).strip() for t in tags_val if t]
            elif isinstance(tags_val, str):
                raw = (
                    tags_val.strip()
                    .replace("[", "")
                    .replace("]", "")
                    .replace('"', "")
                    .replace("'", "")
                )
                metadata["tags"] = [tag.strip() for tag in raw.split(",") if tag.strip()]
    except Exception:
        # 解析失败时使用默认元数据
        pass

    return metadata

