from reborn_core.infrastructure.knowledge.frontmatter import parse_frontmatter
from reborn_core.utils.parsers import parse_think_tags


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


def test_parse_think_tags_with_standard_format():
    """测试标准单行思考与回复"""
    text = "<think>宁宁好像有点累，我不能说教。</think>怎么啦？是不是今天玩太累了？"
    result = parse_think_tags(text)

    assert result["thought"] == "宁宁好像有点累，我不能说教。"
    assert result["response"] == "怎么啦？是不是今天玩太累了？"


def test_parse_think_tags_without_thought():
    """测试模型偶尔遗漏标签的情况（鲁棒性）"""
    text = "爸爸今天给你讲个新故事好不好？"
    result = parse_think_tags(text)

    assert result["thought"] == ""
    assert result["response"] == "爸爸今天给你讲个新故事好不好？"


def test_parse_think_tags_with_multiline_and_spaces():
    """测试多行思考与多余空格"""
    text = """<think>
    第一步：安抚情绪。
    第二步：转移注意力。
    </think>

    过来让爸爸抱抱。
    """
    result = parse_think_tags(text)

    assert "第一步：安抚情绪。" in result["thought"]
    assert result["response"] == "过来让爸爸抱抱。"
