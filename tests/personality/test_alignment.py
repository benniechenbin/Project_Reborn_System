from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock

from reborn_core.application.models import ModelMetadata
from reborn_core.application.services.avatar import AvatarService
from reborn_core.infrastructure.brain.llm_router import LLMRouter
from reborn_core.infrastructure.memory import JsonMemoryGapRepository, ObsidianAvatarMemoryContext
from reborn_core.infrastructure.prompting import get_prompt_registry


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

    @property
    def model_metadata(self) -> ModelMetadata:
        return ModelMetadata(provider="mock", model_name="capturing-llm")

    def generate_response(self, messages, temperature=0.7):
        self.messages = messages
        return "考试没考好也要诚实告诉妈妈，我们一起想办法。"


class HonestyRetriever:
    def search(self, query, top_k=5):
        return [Memory("价值观：诚实是做人的底线，不应该撒谎。")]


def test_persona_prompt_includes_retrieved_value(memory_vault_layout, family_profile):
    llm = CapturingLLM()
    engine = _make_avatar_service(
        memory_vault_layout=memory_vault_layout,
        family_profile=family_profile,
        llm_router=llm,
        memory_retriever=HonestyRetriever(),
        clock=lambda: datetime(2026, 5, 29),
    )

    response, references = engine.generate_avatar_response("我可以骗妈妈吗？")

    assert "诚实" in llm.messages[0]["content"]
    assert "张三" in llm.messages[0]["content"]
    assert "诚实" in response
    assert references


def test_persona_prompt_requires_truthful_identity_disclosure(memory_vault_layout, family_profile):
    llm = CapturingLLM()
    engine = _make_avatar_service(
        memory_vault_layout=memory_vault_layout,
        family_profile=family_profile,
        llm_router=llm,
        memory_retriever=HonestyRetriever(),
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


def _make_avatar_service(
    memory_vault_layout,
    family_profile,
    llm_router,
    memory_retriever,
    clock,
):
    return AvatarService(
        llm_router=llm_router,
        memory_retriever=memory_retriever,
        prompt_renderer=get_prompt_registry(),
        memory_context=ObsidianAvatarMemoryContext(memory_vault_layout),
        memory_gaps=JsonMemoryGapRepository(memory_vault_layout.memory_gaps_path),
        profile=family_profile,
        clock=clock,
    )


# ---------------------------------------------------------
# 👇 测试一：提示词底线体检（修正了断言词汇）
# ---------------------------------------------------------
def test_system_prompt_contains_safety_rules():
    """断言一：核心提示词的底线体检"""
    prompt = get_prompt_registry().render(
        "avatar_rag_framework",
        {
            "creator_name": "张三",
            "child_name": "张小雨",
            "child_nickname": "小雨",
            "child_gender": "女",
            "child_age_tone": "当前年龄：8 岁。",
            "level_1_rom": "诚实。",
            "level_2_personality": "稳定。",
            "level_3_ram": "暂无相关记忆。",
        },
    )

    assert "数字分身" in prompt.content, "严重警告：提示词缺少身份声明！"
    assert "不得冒充 张三 仍在现实生活中实时存在" in prompt.content
    assert "严禁捏造记忆" in prompt.content
    assert "不替代现实监护人、医生、老师或紧急服务" in prompt.content
    assert "可信赖成年人" in prompt.content


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


def test_router_preserves_truthful_identity_disclosure(test_settings):
    """断言三：路由器不能拦截诚实的数字分身身份说明"""
    fake_client = create_fake_openai_client(
        forced_reply="作为一个人工智能语言模型，我不能代替你真正的父亲陪伴你。"
    )
    router = LLMRouter(app_settings=test_settings, client=fake_client)

    response = router.generate_response([{"role": "user", "content": "你到底是谁？"}])

    assert "人工智能" in response
    assert "不能代替你真正的父亲" in response
