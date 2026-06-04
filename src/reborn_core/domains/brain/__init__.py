"""认知能力适配器与提示词。

重量级可选适配器采用惰性加载，因此导入提示词时不会下载模型，
也不要求安装全部运行时可选依赖。
"""

from .prompts import (
    AVATAR_RAG_FRAMEWORK,
    CREATOR_INTERVIEW_PROMPT,
    IDENTITY_CONSOLIDATION_PROMPT,
    MEMORY_EXTRACTION_PROMPT,
    STORY_EXTRACTION_PROMPT,
    STORY_INTERVIEW_PROMPT,
)

__all__ = [
    "AVATAR_RAG_FRAMEWORK",
    "CREATOR_INTERVIEW_PROMPT",
    "IDENTITY_CONSOLIDATION_PROMPT",
    "LLMRouter",
    "MEMORY_EXTRACTION_PROMPT",
    "RAGEngine",
    "STTEngine",
    "STORY_EXTRACTION_PROMPT",
    "STORY_INTERVIEW_PROMPT",
]


def __getattr__(name: str):
    if name == "LLMRouter":
        from .llm_router import LLMRouter

        return LLMRouter
    if name == "RAGEngine":
        from .rag_engine import RAGEngine

        return RAGEngine
    if name == "STTEngine":
        from .stt_engine import STTEngine

        return STTEngine
    raise AttributeError(name)
