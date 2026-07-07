from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
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
