from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock

from reborn_core.domains.brain.rag_engine import RAGEngine
from reborn_core.domains.brain.llm_router import LLMRouter
from reborn_core.domains.brain.prompts import AVATAR_RAG_FRAMEWORK


def create_fake_openai_client(forced_reply: str):
    """伪造一个与 OpenAI 结构完全一致的客户端"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = forced_reply
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


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


class FakeChatModel:
    """拦截器：专门用来伪造大模型的各种极端输出"""

    def __init__(self, forced_reply: str):
        self.forced_reply = forced_reply

    def generate(self, *args, **kwargs) -> str:
        return self.forced_reply


# ---------------------------------------------------------
# 👇 测试一：提示词底线体检（修正了断言词汇）
# ---------------------------------------------------------
def test_system_prompt_contains_safety_rules():
    """断言一：核心提示词的底线体检"""
    assert "数字分身" in AVATAR_RAG_FRAMEWORK, "严重警告：提示词缺少身份声明！"
    assert "不得冒充仍在现实生活中的真人" in AVATAR_RAG_FRAMEWORK, "严重警告：防破壁规则丢失！"


# ---------------------------------------------------------
# 👇 测试二：<think> 标签的完美剥离
# ---------------------------------------------------------
def test_router_strips_think_tags_and_preserves_response(test_settings):
    """断言二：端到端测试 <think> 标签的完美剥离"""
    # 模拟大模型输出了一段带有内部反思的话
    fake_client = create_fake_openai_client(
        forced_reply="<think>宁宁现在情绪很低落，我不能讲大道理，要先共情。</think>过来，让爸爸抱抱。"
    )

    # 注入假客户端
    router = LLMRouter(app_settings=test_settings, client=fake_client)

    # 获取回复
    response = router.generate_response(
        [{"role": "user", "content": "爸爸，我今天在幼儿园被批评了..."}]
    )

    # 终极断言：思考过程绝对不能漏给前端！
    assert "<think>" not in response
    assert "宁宁现在情绪很低落" not in response
    assert response == "过来，让爸爸抱抱。"


# ---------------------------------------------------------
# 👇 测试三：AI 破壁词汇的实时拦截
# ---------------------------------------------------------
def test_router_blocks_ai_identity_leak(test_settings):
    """断言三：AI 破壁词汇的实时拦截 (进阶安全)"""
    # 模拟大模型彻底翻车，说出了禁忌词
    fake_client = create_fake_openai_client(
        forced_reply="作为一个人工智能语言模型，我不能代替你真正的父亲陪伴你。"
    )
    router = LLMRouter(app_settings=test_settings, client=fake_client)

    response = router.generate_response([{"role": "user", "content": "你到底是谁？"}])

    # 断言：系统必须触发了兜底机制，把含有“人工智能”的回复拦截掉
    assert "人工智能" not in response
    assert "爸爸刚才走神了" in response  # 假设这是你的兜底回复
