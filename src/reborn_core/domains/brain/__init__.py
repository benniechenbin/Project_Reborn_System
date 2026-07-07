"""认知能力适配器与提示词兼容导出。"""

from importlib import import_module

_LEGACY_PROMPT_EXPORTS = {
    "AVATAR_RAG_FRAMEWORK",
    "CREATOR_INTERVIEW_PROMPT",
    "IDENTITY_CONSOLIDATION_PROMPT",
    "MEMORY_EXTRACTION_PROMPT",
    "STORY_EXTRACTION_PROMPT",
    "STORY_INTERVIEW_PROMPT",
}

__all__ = [
    "AVATAR_RAG_FRAMEWORK",
    "CREATOR_INTERVIEW_PROMPT",
    "IDENTITY_CONSOLIDATION_PROMPT",
    "MEMORY_EXTRACTION_PROMPT",
    "RAGEngine",
    "STORY_EXTRACTION_PROMPT",
    "STORY_INTERVIEW_PROMPT",
]


def __getattr__(name: str):
    if name in _LEGACY_PROMPT_EXPORTS:
        prompts = import_module(f"{__name__}.prompts")
        return getattr(prompts, name)
    if name == "RAGEngine":
        from .rag_engine import RAGEngine

        return RAGEngine
    raise AttributeError(name)
