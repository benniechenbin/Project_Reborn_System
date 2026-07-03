"""Deprecated compatibility facade for versioned Markdown prompts.

New code should use ``reborn_core.domains.brain.prompt_registry`` directly.
The constants below expose unrendered templates for legacy imports only.
"""

from .prompt_registry import get_prompt_registry


def _template_message(prompt_id: str) -> dict[str, str]:
    template = get_prompt_registry().load(prompt_id)
    return template.as_message()


CREATOR_INTERVIEW_PROMPT = _template_message("creator_interview")
MEMORY_EXTRACTION_PROMPT = _template_message("memory_extraction")
STORY_INTERVIEW_PROMPT = _template_message("story_interview")
STORY_EXTRACTION_PROMPT = _template_message("story_extraction")
IDENTITY_CONSOLIDATION_PROMPT = _template_message("identity_consolidation")
AVATAR_RAG_FRAMEWORK = get_prompt_registry().load("avatar_rag_framework").template


__all__ = [
    "AVATAR_RAG_FRAMEWORK",
    "CREATOR_INTERVIEW_PROMPT",
    "IDENTITY_CONSOLIDATION_PROMPT",
    "MEMORY_EXTRACTION_PROMPT",
    "STORY_EXTRACTION_PROMPT",
    "STORY_INTERVIEW_PROMPT",
]
