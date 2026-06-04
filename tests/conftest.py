import pytest

from reborn_core.config import Settings


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        _env_file=None,
        base_dir=tmp_path,
        child_name="张小明",
        child_nickname="明明",
        child_gender="男",
        child_birthday="2020-01-01",
    )
