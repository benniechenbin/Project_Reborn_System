import pytest

from reborn_core.domains.brain.prompt_registry import (
    PromptRegistry,
    PromptRegistryError,
    get_prompt_registry,
)


def test_prompt_registry_renders_declared_variables():
    registry = get_prompt_registry()

    rendered = registry.render(
        "creator_interview",
        {"creator_name": "张三", "child_nickname": "小雨"},
    )

    assert rendered.prompt_id == "creator_interview"
    assert "张三" in rendered.content
    assert "小雨" in rendered.content
    assert rendered.role == "system"
    assert len(rendered.sha256) == 64


def test_prompt_registry_rejects_missing_variables():
    registry = get_prompt_registry()

    with pytest.raises(PromptRegistryError, match="CREATOR_NAME"):
        registry.render("creator_interview", {"child_nickname": "小雨"})


def test_prompt_registry_rejects_undeclared_variables():
    registry = get_prompt_registry()

    with pytest.raises(PromptRegistryError, match="undeclared"):
        registry.render(
            "creator_interview",
            {
                "creator_name": "张三",
                "child_nickname": "小雨",
                "unexpected": "value",
            },
        )


def test_prompt_registry_reports_context_variables_not_provided():
    registry = get_prompt_registry()

    with pytest.raises(PromptRegistryError, match="not provided by caller context"):
        registry.render_from_context("creator_interview", {"creator_name": "张三"})


def test_prompt_registry_allows_unknown_braces_inside_fenced_code_blocks(tmp_path):
    prompt_file = tmp_path / "sample.md"
    prompt_file.write_text(
        """---
prompt_id: sample
version: 1.0.0
role: system
variables: [name]
---
Hello {name}.

```markdown
date: {date}
```
""",
        encoding="utf-8",
    )

    rendered = PromptRegistry(tmp_path).render("sample", {"name": "张三"})

    assert "Hello 张三." in rendered.content
    assert "date: {date}" in rendered.content


def test_prompt_registry_rejects_unknown_braces_outside_fenced_code_blocks(tmp_path):
    prompt_file = tmp_path / "sample.md"
    prompt_file.write_text(
        """---
prompt_id: sample
version: 1.0.0
role: system
variables: [name]
---
Hello {name} on {date}.
""",
        encoding="utf-8",
    )

    with pytest.raises(PromptRegistryError, match="undeclared variables: date"):
        PromptRegistry(tmp_path).render("sample", {"name": "张三"})


def test_prompt_registry_rejects_variables_used_only_inside_fenced_code_blocks(tmp_path):
    prompt_file = tmp_path / "sample.md"
    prompt_file.write_text(
        """---
prompt_id: sample
version: 1.0.0
role: system
variables: [name]
---
```markdown
person: {name}
```
""",
        encoding="utf-8",
    )

    with pytest.raises(PromptRegistryError, match="declares unused variables: name"):
        PromptRegistry(tmp_path).render("sample", {"name": "张三"})


def test_prompt_sha256_tracks_rendered_content():
    registry = get_prompt_registry()
    base = {
        "creator_name": "张三",
        "child_name": "张小雨",
        "child_nickname": "小雨",
        "child_gender": "女",
        "child_age_tone": "当前年龄：8 岁。",
        "level_1_rom": "诚实。",
        "level_2_personality": "稳定。",
        "level_3_ram": "记忆 A。",
    }

    first = registry.render("avatar_rag_framework", base)
    second = registry.render("avatar_rag_framework", {**base, "level_3_ram": "记忆 B。"})

    assert first.sha256 != second.sha256


def test_prompt_sources_do_not_contain_private_hardcoded_names():
    registry = get_prompt_registry()
    prompt_text = "\n".join(
        path.read_text(encoding="utf-8") for path in registry.root.rglob("*.md")
    )

    for forbidden in ("陈斌", "宁宁", "张三", "张小明", "明明"):
        assert forbidden not in prompt_text
