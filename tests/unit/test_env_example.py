from scripts.generate_env_example import build_env_example


def test_env_example_uses_defaults_and_hides_secrets():
    content = build_env_example()

    assert "LOG_DIR=logs" in content
    assert "LLM_MODEL_NAME=deepseek-chat" in content
    assert "LLM_API_KEY=\n" in content
    assert "BACKUP_ENCRYPTION_KEY=\n" in content
    assert "BACKUP_REQUIRE_ENCRYPTION=true" in content
    assert "BASE_DIR=" not in content
