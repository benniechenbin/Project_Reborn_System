"""认知层：语音、大模型路由、RAG 与提示词。"""

from .llm_router import LLMRouter
from .prompts import (
    AVATAR_RAG_FRAMEWORK,
    CREATOR_INTERVIEW_PROMPT,
    IDENTITY_CONSOLIDATION_PROMPT,
    MEMORY_EXTRACTION_PROMPT,
    STORY_EXTRACTION_PROMPT,
    STORY_INTERVIEW_PROMPT,
)
from .rag_engine import RAGEngine
from .stt_engine import STTEngine

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
