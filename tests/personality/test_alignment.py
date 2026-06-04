from dataclasses import dataclass, field
from datetime import datetime

from reborn_core.domains.brain.rag_engine import RAGEngine


@dataclass
class Memory:
    page_content: str
    metadata: dict = field(default_factory=lambda: {"rerank_score": 0.9})


class CapturingLLM:
    def __init__(self):
        self.messages = []

    def generate_response(self, messages, temperature=0.7):
        self.messages = messages
        return "考试没考好也要诚实告诉妈妈，我们一起想办法。"


class HonestyRetriever:
    def search(self, query, top_k=5):
        return [Memory("价值观：诚实是做人的底线，不应该撒谎。")]


def test_persona_prompt_includes_retrieved_value(test_settings):
    llm = CapturingLLM()
    engine = RAGEngine(
        app_settings=test_settings,
        llm_router=llm,
        vector_db=HonestyRetriever(),
        clock=lambda: datetime(2026, 5, 29),
    )

    response, references = engine.generate_avatar_response("我可以骗妈妈吗？")

    assert "诚实" in llm.messages[0]["content"]
    assert "诚实" in response
    assert references


def test_persona_prompt_requires_truthful_identity_disclosure(test_settings):
    llm = CapturingLLM()
    engine = RAGEngine(
        app_settings=test_settings,
        llm_router=llm,
        vector_db=HonestyRetriever(),
        clock=lambda: datetime(2026, 5, 29),
    )

    engine.generate_avatar_response("你是真的爸爸吗？")

    assert "必须用适龄、诚实且温和的方式说明你是数字分身" in llm.messages[0]["content"]
