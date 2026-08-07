from pathlib import Path

import pytest

from reborn_core.config import Settings
from reborn_core.config import settings as settings_module


@pytest.mark.parametrize(
    ("system_name", "expected_attribute"),
    [
        ("Windows", "obsidian_vault_path_win"),
        ("Darwin", "obsidian_vault_path_mac"),
    ],
)
def test_active_obsidian_path_uses_platform_specific_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system_name: str,
    expected_attribute: str,
) -> None:
    windows_path = tmp_path / "windows" / "Project_Reborn_System"
    mac_path = tmp_path / "mac" / "Project_Reborn_System"
    settings = Settings.model_construct(
        base_dir=tmp_path,
        obsidian_vault_path_win=windows_path,
        obsidian_vault_path_mac=mac_path,
    )
    monkeypatch.setattr(settings_module.platform, "system", lambda: system_name)

    assert settings.active_obsidian_path == getattr(settings, expected_attribute)


def test_default_memory_layout_uses_governed_names(tmp_path: Path) -> None:
    settings = Settings.model_construct(base_dir=tmp_path)

    assert settings.core_values_folder == "30_Values"
    assert settings.stories_folder == "40_Stories"
    assert settings.ai_reflections_folder == "20_AI_Reflections"
    assert settings.identity_history_folder == "10_Identity_History"
    assert settings.source_artifacts_folder == "20_Source_Artifacts"
    assert settings.memory_index_folders == ("30_Values", "40_Stories")


def test_explicit_memory_index_folders_take_precedence(tmp_path: Path) -> None:
    settings = Settings.model_construct(
        base_dir=tmp_path,
        REBORN_TARGET_FOLDERS=("custom_values", "custom_stories"),
    )

    assert settings.memory_index_folders == ("custom_values", "custom_stories")
