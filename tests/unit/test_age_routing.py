from datetime import datetime

import pytest

from reborn_core.domains.brain.rag_engine import RAGEngine


class StubLLM:
    def generate_response(self, messages, temperature=0.7):
        return "stub"


class StubRetriever:
    def search(self, query, top_k=5):
        return []


@pytest.mark.parametrize(
    ("birthday", "expected_age", "expected_tone"),
    [
        ("2022-01-01", "4 岁", "温柔、带有童话色彩"),
        ("2011-01-01", "15 岁", "极客幽默"),
        ("2001-01-01", "25 岁", "成年人之间深沉、平等"),
    ],
)
def test_calculate_child_age_and_tone(
    test_settings,
    birthday,
    expected_age,
    expected_tone,
):
    settings = test_settings.model_copy(update={"child_birthday": birthday})
    engine = RAGEngine(
        app_settings=settings,
        llm_router=StubLLM(),
        vector_db=StubRetriever(),
        clock=lambda: datetime(2026, 5, 29),
    )

    tone_info = engine._calculate_child_age_and_tone()

    assert expected_age in tone_info
    assert expected_tone in tone_info
    assert "明明" in tone_info
