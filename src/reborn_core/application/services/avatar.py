from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from reborn_core.application.ports import (
    AvatarMemoryContextPort,
    ChatModel,
    MemoryGapRepositoryPort,
    MemoryRetriever,
    PromptRendererPort,
)
from reborn_core.domains import FamilyProfile
from reborn_core.domains.brain.age_tone import build_child_age_tone
from reborn_core.observability import logger


class AvatarService:
    """Generates avatar sandbox replies from governed identity and retrievable memories."""

    def __init__(
        self,
        llm_router: ChatModel,
        memory_retriever: MemoryRetriever,
        prompt_renderer: PromptRendererPort,
        memory_context: AvatarMemoryContextPort,
        memory_gaps: MemoryGapRepositoryPort,
        profile: FamilyProfile,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.llm_router = llm_router
        self.memory_retriever = memory_retriever
        self.prompt_renderer = prompt_renderer
        self.memory_context = memory_context
        self.memory_gaps = memory_gaps
        self.profile = profile
        self.clock = clock or (lambda: datetime.now(UTC))

    def generate_avatar_response(
        self,
        user_query: str,
        chat_history: list[dict[str, str]] | None = None,
        *,
        temperature: float = 0.7,
        record_memory_gap: bool = True,
    ) -> tuple[str, list[Any]]:
        l1 = self._get_level_1_rom()
        l2 = self._get_level_2_personality()
        l3_text, max_score, references = self._get_level_3_ram(user_query)

        if record_memory_gap and max_score < -0.8:
            self._record_memory_gap(user_query, max_score)

        full_system_prompt = self.prompt_renderer.render(
            "avatar_rag_framework",
            {
                "creator_name": self.profile.creator.name,
                "child_name": self.profile.child.name,
                "child_nickname": self.profile.child.nickname,
                "child_gender": self.profile.child.gender.value,
                "child_age_tone": self._calculate_child_age_and_tone(),
                "level_1_rom": l1,
                "level_2_personality": l2,
                "level_3_ram": l3_text,
            },
        ).content

        messages: list[dict[str, str]] = [{"role": "system", "content": full_system_prompt}]
        if chat_history:
            history = [message for message in chat_history if message["role"] != "system"][-10:]
            messages.extend(history)
        messages.append({"role": "user", "content": user_query})

        logger.info("Avatar is generating a response. RAM recall score: {}", max_score)
        response_text = self.llm_router.generate_response(messages, temperature=temperature)
        return response_text, references

    def _calculate_child_age_and_tone(self) -> str:
        return build_child_age_tone(
            child_name=self.profile.child.name,
            child_nickname=self.profile.child.nickname,
            child_gender=self.profile.child.gender.value,
            child_birthday=self.profile.child.birthday,
            now=self.clock(),
        )

    def _get_level_1_rom(self) -> str:
        return self.memory_context.load_level_1_rom(self.clock())

    def _get_level_2_personality(self) -> str:
        return self.memory_context.load_level_2_personality()

    def _get_level_3_ram(self, query: str) -> tuple[str, float, list[Any]]:
        try:
            memories = self.memory_retriever.search(query, top_k=3)
            if not memories:
                return "（此刻脑海中没有想起具体的往事细节）", -1.0, []

            max_score = memories[0].metadata.get("rerank_score", 0.0)
            ram_text = "\n".join([f"- {doc.page_content}" for doc in memories])
            return ram_text, max_score, memories
        except Exception as exc:
            logger.error("RAM 检索失败: {}", exc)
            return "（记忆通路暂时阻塞）", -1.0, []

    def _record_memory_gap(self, query: str, score: float) -> None:
        self.memory_gaps.record_gap(query, score, self.clock())
