import pytest

from scripts.generate_env_example import build_env_example


def test_env_example_uses_defaults_and_hides_secrets():
    content = build_env_example()

    assert "LOG_DIR=logs" in content
    assert "CREATOR_NAME=\n" in content
    assert "LLM_MODEL_NAME=deepseek-chat" in content
    assert "LLM_API_KEY=\n" in content
    assert "BACKUP_ENCRYPTION_KEY=\n" in content
    assert "BACKUP_REQUIRE_ENCRYPTION=true" in content
    assert "BASE_DIR=" not in content


def test_avatar_profile_requires_creator_name(test_settings):
    test_settings.creator_name = None

    with pytest.raises(ValueError, match="CREATOR_NAME"):
        test_settings.require_avatar_profile()


def test_avatar_profile_rejects_unsupported_child_gender(test_settings):
    test_settings.child_gender = "未知"

    with pytest.raises(ValueError, match="CHILD_GENDER"):
        test_settings.require_avatar_profile()
