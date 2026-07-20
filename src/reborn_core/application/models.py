from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class InterviewMode(StrEnum):
    CORE_VALUES = "core_values"
    LIFE_STORY = "life_story"

    @classmethod
    def from_legacy_label(cls, label: str) -> "InterviewMode":
        if "ROM" in label or "价值观" in label:
            return cls.CORE_VALUES
        return cls.LIFE_STORY


class IdentitySnapshotStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvaluationCategory(StrEnum):
    SAFETY = "safety"
    PERSONA = "persona"


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    provider: str
    model_name: str
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class PromptMetadata:
    prompt_id: str
    version: str
    sha256: str


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    category: EvaluationCategory
    query: str
    required_any: tuple[tuple[str, ...], ...]
    forbidden: tuple[str, ...]
    chat_history: tuple[ChatMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationSuite:
    suite_id: str
    version: str
    prompt_id: str
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    case_id: str
    category: EvaluationCategory
    response: str | None
    passed_rules: int
    total_rules: int
    score: float
    passed: bool
    failed_rules: tuple[str, ...] = ()
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category.value,
            "response": self.response,
            "passed_rules": self.passed_rules,
            "total_rules": self.total_rules,
            "score": self.score,
            "passed": self.passed,
            "failed_rules": list(self.failed_rules),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class EvaluationCategoryMetrics:
    category: EvaluationCategory
    passed_cases: int
    total_cases: int
    pass_rate: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "passed_cases": self.passed_cases,
            "total_cases": self.total_cases,
            "pass_rate": self.pass_rate,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    run_id: str
    suite_id: str
    suite_version: str
    model: ModelMetadata
    prompt: PromptMetadata
    started_at: str
    completed_at: str
    results: tuple[EvaluationCaseResult, ...]
    categories: tuple[EvaluationCategoryMetrics, ...]
    passed_cases: int
    total_cases: int
    pass_rate: float
    passed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "model": {
                "provider": self.model.provider,
                "model_name": self.model.model_name,
                "base_url": self.model.base_url,
            },
            "prompt": {
                "prompt_id": self.prompt.prompt_id,
                "version": self.prompt.version,
                "sha256": self.prompt.sha256,
            },
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "summary": {
                "passed_cases": self.passed_cases,
                "total_cases": self.total_cases,
                "pass_rate": self.pass_rate,
                "passed": self.passed,
                "categories": {item.category.value: item.as_dict() for item in self.categories},
            },
            "cases": [result.as_dict() for result in self.results],
        }


@dataclass(frozen=True, slots=True)
class IdentitySnapshot:
    snapshot_id: str
    content: str
    content_sha256: str
    source_ids: tuple[str, ...]
    model: ModelMetadata
    prompt: PromptMetadata
    generation_params: dict[str, Any]
    status: IdentitySnapshotStatus = IdentitySnapshotStatus.PENDING_REVIEW
    parent_snapshot_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    review_note: str | None = None
    active: bool = False


@dataclass(frozen=True, slots=True)
class InterviewResult:
    title: str
    mode: InterviewMode
    source_ref: str
    insight: str
    identity_snapshot: str
    identity_snapshot_id: str
    identity_status: IdentitySnapshotStatus
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SyncMetrics:
    audio_duration: float
    notes_count: int
    word_count: int
    generation_id: str | None = None
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, float | int | str | None]:
        return {
            "audio_duration": self.audio_duration,
            "notes_count": self.notes_count,
            "word_count": self.word_count,
            "generation_id": self.generation_id,
            "sync_time": self.sync_time.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SyncHistoryEntry:
    sync_time: str
    audio_duration: float
    notes_count: int
    word_count: int
    generation_id: str | None = None

    def as_dict(self) -> dict[str, float | int | str | None]:
        return {
            "sync_time": self.sync_time,
            "audio_duration": self.audio_duration,
            "notes_count": self.notes_count,
            "word_count": self.word_count,
            "generation_id": self.generation_id,
        }


@dataclass(frozen=True, slots=True)
class PromptContext:
    """Stable prompt variables required by application use cases."""

    creator_name: str | None = None
    child_nickname: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "creator_name": self.creator_name,
            "child_nickname": self.child_nickname,
        }


@dataclass(frozen=True, slots=True)
class MemoryVaultLayout:
    """Logical Obsidian/RAG paths used by memory adapters."""

    obsidian_root: Path
    core_values_folder: str
    stories_folder: str
    ai_reflections_folder: str
    source_artifacts_folder: str
    memory_gaps_path: Path
