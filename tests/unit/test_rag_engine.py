import pytest
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock
from reborn_core.domains.brain.rag_engine import RAGEngine


@dataclass
class Memory:
    page_content: str
    metadata: dict = field(default_factory=dict)


@pytest.fixture
def mock_dependencies():
    llm_router = MagicMock()
    llm_router.generate_response.return_value = "I am your father."

    vector_db = MagicMock()
    # Default: return some documents
    doc = Memory(page_content="I remember when you were born.", metadata={"rerank_score": 0.9})
    vector_db.search.return_value = [doc]

    return llm_router, vector_db


@pytest.fixture
def rag_engine(test_settings, mock_dependencies):
    llm_router, vector_db = mock_dependencies

    def mock_clock():
        return datetime(2026, 6, 4)

    engine = RAGEngine(
        app_settings=test_settings, llm_router=llm_router, vector_db=vector_db, clock=mock_clock
    )
    return engine


def test_rag_age_routing_child(rag_engine):
    # Child is born 2020-01-01, in 2026-06-04 age is 6
    # Wait, 2026 - 2020 = 6.
    # Let's check the logic: age < 6 is fairy tale, age < 13 is encouraging.
    # At age 6, it should be the 2nd tier.
    tone_info = rag_engine._calculate_child_age_and_tone()
    assert "大约 6 岁" in tone_info
    assert "鼓励、引导" in tone_info


def test_rag_age_routing_toddler(test_settings, mock_dependencies):
    llm_router, vector_db = mock_dependencies
    test_settings.child_birthday = "2023-01-01"  # age 3
    engine = RAGEngine(
        app_settings=test_settings,
        llm_router=llm_router,
        vector_db=vector_db,
        clock=lambda: datetime(2026, 6, 4),
    )

    tone_info = engine._calculate_child_age_and_tone()
    assert "大约 3 岁" in tone_info
    assert "温柔、带有童话色彩" in tone_info


def test_rag_age_routing_teenager(test_settings, mock_dependencies):
    llm_router, vector_db = mock_dependencies
    test_settings.child_birthday = "2010-01-01"  # age 16
    engine = RAGEngine(
        app_settings=test_settings,
        llm_router=llm_router,
        vector_db=vector_db,
        clock=lambda: datetime(2026, 6, 4),
    )

    tone_info = engine._calculate_child_age_and_tone()
    assert "大约 16 岁" in tone_info
    assert "开明、带点极客幽默" in tone_info


def test_rag_age_routing_adult(test_settings, mock_dependencies):
    llm_router, vector_db = mock_dependencies
    test_settings.child_birthday = "1990-01-01"  # age 36
    engine = RAGEngine(
        app_settings=test_settings,
        llm_router=llm_router,
        vector_db=vector_db,
        clock=lambda: datetime(2026, 6, 4),
    )

    tone_info = engine._calculate_child_age_and_tone()
    assert "大约 36 岁" in tone_info
    assert "深沉、平等" in tone_info


def test_rag_get_level_1_rom(rag_engine, tmp_path):
    # Mock some files
    rag_engine.core_memories_path.mkdir(parents=True, exist_ok=True)
    (rag_engine.core_memories_path / "00_Master_Identity.md").write_text(
        "I am a father.", encoding="utf-8"
    )
    (rag_engine.core_memories_path / "03_Prime_Directives.md").write_text(
        "Rule 1: Be kind.", encoding="utf-8"
    )

    rom = rag_engine._get_level_1_rom()
    assert "I am a father." in rom
    assert "Rule 1: Be kind." in rom
    assert "当前现实时间：2026-06-04" in rom


def test_rag_get_level_2_personality(rag_engine):
    rag_engine.reflections_path.mkdir(parents=True, exist_ok=True)
    (rag_engine.reflections_path / "reflection1.md").write_text(
        "Today I learned patience.", encoding="utf-8"
    )

    personality = rag_engine._get_level_2_personality()
    assert "Today I learned patience." in personality


def test_rag_get_level_2_personality_empty(rag_engine):
    assert "暂无" in rag_engine._get_level_2_personality()


def test_rag_get_level_3_ram_success(rag_engine, mock_dependencies):
    _, vector_db = mock_dependencies
    doc = Memory(page_content="Memory 1", metadata={"rerank_score": 0.8})
    vector_db.search.return_value = [doc]

    text, score, refs = rag_engine._get_level_3_ram("test query")
    assert "Memory 1" in text
    assert score == 0.8
    assert len(refs) == 1


def test_rag_get_level_3_ram_empty(rag_engine, mock_dependencies):
    _, vector_db = mock_dependencies
    vector_db.search.return_value = []

    text, score, refs = rag_engine._get_level_3_ram("test query")
    assert "没有想起" in text
    assert score == -1.0
    assert refs == []


def test_rag_record_memory_gap(rag_engine):
    rag_engine._record_memory_gap("unknown topic", -0.9)
    assert rag_engine.gap_file.exists()

    gaps = json.loads(rag_engine.gap_file.read_text(encoding="utf-8"))
    assert len(gaps) == 1
    assert gaps[0]["query"] == "unknown topic"
    assert gaps[0]["score"] == -0.9


def test_rag_record_memory_gap_is_thread_safe(rag_engine):
    def record(index):
        rag_engine._record_memory_gap(f"unknown topic {index}", -0.9)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record, range(20)))

    gaps = json.loads(rag_engine.gap_file.read_text(encoding="utf-8"))
    assert len(gaps) == 20
    assert {gap["query"] for gap in gaps} == {f"unknown topic {index}" for index in range(20)}


def test_generate_avatar_response(rag_engine, mock_dependencies):
    llm_router, _ = mock_dependencies
    response, refs = rag_engine.generate_avatar_response("Tell me a story.")

    assert response == "I am your father."
    assert len(refs) == 1
    llm_router.generate_response.assert_called_once()
