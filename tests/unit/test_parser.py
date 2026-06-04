from reborn_core.infrastructure.knowledge.frontmatter import parse_frontmatter


def test_parse_frontmatter_standard():
    content = """---
date: "2024-05-20"
tags: [重要, 价值观]
---
这是正文内容。"""
    meta = parse_frontmatter(content)
    assert meta["date"] == "2024-05-20"
    assert "重要" in meta["tags"]
    assert "价值观" in meta["tags"]


def test_parse_frontmatter_different_date_format():
    content = """---
date: 2024/05/20
tags: 故事, 童年
---"""
    meta = parse_frontmatter(content)
    assert meta["date"] == "2024-05-20"
    assert "故事" in meta["tags"]
    assert "童年" in meta["tags"]


def test_parse_frontmatter_missing_yaml():
    content = "这就是一段没有 YAML 的普通文字。"
    meta = parse_frontmatter(content)
    assert meta["date"] == "未知日期"
    assert meta["tags"] == []
