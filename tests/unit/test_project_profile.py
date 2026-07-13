from datetime import date

import pytest

from reborn_core.domains import ChildGender
from reborn_core.infrastructure.profile import (
    ProjectProfileError,
    TomlFamilyProfileRepository,
)


def test_project_profile_loader_reads_family_profile(tmp_path):
    path = tmp_path / "project_profile.toml"
    path.write_text(
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

    profile = TomlFamilyProfileRepository(path).load()

    assert profile.creator.name == "张三"
    assert profile.child.name == "张小明"
    assert profile.child.nickname == "明明"
    assert profile.child.gender is ChildGender.MALE
    assert profile.child.birthday == date(2020, 1, 1)


def test_project_profile_loader_reports_missing_required_sections(tmp_path):
    path = tmp_path / "project_profile.toml"
    path.write_text('[creator]\nname = "张三"\n', encoding="utf-8")

    with pytest.raises(ProjectProfileError, match=r"\[child\]"):
        TomlFamilyProfileRepository(path).load()


def test_project_profile_loader_reports_unsupported_child_gender(tmp_path):
    path = tmp_path / "project_profile.toml"
    path.write_text(
        """[creator]
name = "张三"

[child]
name = "张小明"
nickname = "明明"
gender = "未知"
birthday = "2020-01-01"
""",
        encoding="utf-8",
    )

    with pytest.raises(ProjectProfileError, match="'男' or '女'"):
        TomlFamilyProfileRepository(path).load()


def test_project_profile_loader_reports_invalid_birthday(tmp_path):
    path = tmp_path / "project_profile.toml"
    path.write_text(
        """[creator]
name = "张三"

[child]
name = "张小明"
nickname = "明明"
gender = "男"
birthday = "2020/01/01"
""",
        encoding="utf-8",
    )

    with pytest.raises(ProjectProfileError, match="YYYY-MM-DD"):
        TomlFamilyProfileRepository(path).load()
