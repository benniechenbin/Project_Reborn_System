from datetime import date, datetime

import pytest

from reborn_core.domains.brain.age_tone import build_child_age_tone


@pytest.mark.parametrize(
    ("birthday", "expected_age", "expected_tone"),
    [
        ("2022-01-01", "4 岁", "温柔、带有童话色彩"),
        ("2011-01-01", "15 岁", "极客幽默"),
        ("2001-01-01", "25 岁", "成年人之间深沉、平等"),
    ],
)
def test_calculate_child_age_and_tone(birthday, expected_age, expected_tone):
    tone_info = build_child_age_tone(
        child_name="张小明",
        child_nickname="明明",
        child_gender="男",
        child_birthday=date.fromisoformat(birthday),
        now=datetime(2026, 5, 29),
    )

    assert expected_age in tone_info
    assert expected_tone in tone_info
    assert "明明" in tone_info
