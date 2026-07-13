from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ChildGender(StrEnum):
    """Supported child gender values for current avatar tone rules."""

    MALE = "男"
    FEMALE = "女"

    @classmethod
    def parse(cls, value: object) -> "ChildGender":
        try:
            return cls(str(value).strip())
        except ValueError as exc:
            raise ValueError("Child gender must be '男' or '女'.") from exc


@dataclass(frozen=True, slots=True)
class CreatorProfile:
    """Business identity for the creator represented by the digital companion."""

    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Creator name is required.")


@dataclass(frozen=True, slots=True)
class ChildProfile:
    """Business identity and age-routing facts for the child."""

    name: str
    nickname: str
    gender: ChildGender
    birthday: date

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Child name is required.")
        if not self.nickname.strip():
            raise ValueError("Child nickname is required.")
        if not isinstance(self.gender, ChildGender):
            raise ValueError("Child gender must be a ChildGender value.")
        if not isinstance(self.birthday, date):
            raise ValueError("Child birthday must be a date.")


@dataclass(frozen=True, slots=True)
class FamilyProfile:
    """Domain profile for the family that Project Reborn serves."""

    creator: CreatorProfile
    child: ChildProfile
