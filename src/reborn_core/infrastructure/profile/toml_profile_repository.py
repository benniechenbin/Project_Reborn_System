from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Any

from reborn_core.domains import ChildGender, ChildProfile, CreatorProfile, FamilyProfile


class ProjectProfileError(ValueError):
    """Raised when the project family profile file is missing or invalid."""


class TomlFamilyProfileRepository:
    """Loads the local family profile from a TOML project data file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> FamilyProfile:
        if not self.path.exists():
            raise ProjectProfileError(
                f"Project profile file not found: {self.path}. "
                "Create it from docs/examples/project_profile.toml."
            )
        try:
            payload = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ProjectProfileError(f"Invalid project profile TOML: {exc}") from exc
        return family_profile_from_mapping(payload)


def family_profile_from_mapping(payload: dict[str, Any]) -> FamilyProfile:
    creator = _section(payload, "creator")
    child = _section(payload, "child")
    return FamilyProfile(
        creator=CreatorProfile(name=_required_text(creator, "name", "creator.name")),
        child=ChildProfile(
            name=_required_text(child, "name", "child.name"),
            nickname=_required_text(child, "nickname", "child.nickname"),
            gender=_required_gender(child),
            birthday=_required_date(child, "birthday", "child.birthday"),
        ),
    )


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    section = payload.get(key)
    if not isinstance(section, dict):
        raise ProjectProfileError(f"Project profile requires [{key}] section.")
    return section


def _required_text(section: dict[str, Any], key: str, label: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProjectProfileError(f"Project profile requires {label}.")
    return value.strip()


def _required_date(section: dict[str, Any], key: str, label: str) -> date:
    value = section.get(key)
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ProjectProfileError(f"Project profile {label} must use YYYY-MM-DD.") from exc
    raise ProjectProfileError(f"Project profile requires {label}.")


def _required_gender(section: dict[str, Any]) -> ChildGender:
    value = _required_text(section, "gender", "child.gender")
    try:
        return ChildGender.parse(value)
    except ValueError as exc:
        raise ProjectProfileError("Project profile child.gender must be '男' or '女'.") from exc
