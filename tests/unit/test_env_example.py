import subprocess
import sys
from pathlib import Path

from reborn_core import config
from scripts.generate_env_example import DEFAULT_OUTPUT_FILE, build_env_example


def test_default_env_example_output_points_to_project_root():
    project_root = Path(__file__).parents[2]

    assert DEFAULT_OUTPUT_FILE == project_root / ".env.example"


def test_script_check_works_from_outside_project_root(tmp_path):
    project_root = Path(__file__).parents[2]
    script = project_root / "scripts" / "generate_env_example.py"

    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_env_example_uses_defaults_and_hides_secrets():
    content = build_env_example()

    assert "LOG_DIR=logs" in content
    assert "PROJECT_PROFILE_PATH=data/project_profile.toml" in content
    assert "CREATOR_NAME=" not in content
    assert "CHILD_NAME=" not in content
    assert "CHILD_NICKNAME=" not in content
    assert "CHILD_GENDER=" not in content
    assert "CHILD_BIRTHDAY=" not in content
    assert "LLM_MODEL_NAME=deepseek-chat" in content
    assert "STT_ENDPOINT=local" in content
    assert "例如 https://api.openai.com/v1 切换云端转写。" in content
    assert "STT_MODEL_NAME=paraformer-zh" in content
    assert "STT_LOCAL_ENGINE=funasr" in content
    assert "STT_PROVIDER=" not in content
    assert "FUNASR_MODEL_NAME=" not in content
    assert "LLM_API_KEY=\n" in content
    assert "BACKUP_ENCRYPTION_KEY=\n" in content
    assert "BACKUP_REQUIRE_ENCRYPTION=true" in content
    assert "BASE_DIR=" not in content


def test_checked_in_env_example_is_current():
    env_example = Path(__file__).parents[2] / ".env.example"

    assert env_example.read_text(encoding="utf-8") == build_env_example()


def test_config_package_does_not_export_eager_settings_singleton():
    assert "settings" not in config.__all__
    assert not isinstance(getattr(config, "settings", None), config.Settings)
