import pytest

from reborn_core.application.models import MemoryVaultLayout, PromptContext
from reborn_core.config import Settings
from reborn_core.infrastructure.profile import TomlFamilyProfileRepository
from reborn_core.infrastructure.prompting import get_prompt_registry


@pytest.fixture
def test_settings(tmp_path):
    profile_path = tmp_path / "data" / "project_profile.toml"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        """[creator]
name = "张三"

[child]
name = "张小明"
nickname = "明明"
gender = "男"
birthday = "2020-01-01"
""",
        encoding="utf-8",
    )
    return Settings(
        _env_file=None,
        base_dir=tmp_path,
        obsidian_vault_path_win=None,
        obsidian_vault_path_mac=None,
        llm_api_key="sk-mock-key-for-testing",
    )


@pytest.fixture
def family_profile(test_settings):
    return TomlFamilyProfileRepository(test_settings.resolved_project_profile_path).load()


@pytest.fixture
def prompt_context(family_profile):
    return PromptContext(
        creator_name=family_profile.creator.name,
        child_nickname=family_profile.child.nickname,
    )


@pytest.fixture
def prompt_renderer():
    return get_prompt_registry()


@pytest.fixture
def memory_vault_layout(test_settings):
    obsidian_root = test_settings.active_obsidian_path or (
        test_settings.base_dir / "data" / "memories"
    )
    return MemoryVaultLayout(
        obsidian_root=obsidian_root,
        core_values_folder=test_settings.core_values_folder,
        stories_folder=test_settings.stories_folder,
        ai_reflections_folder=test_settings.ai_reflections_folder,
        source_artifacts_folder=test_settings.source_artifacts_folder,
        memory_gaps_path=test_settings.resolved_memory_gaps_path,
    )
