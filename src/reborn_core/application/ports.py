from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    SyncHistoryEntry,
)
from reborn_core.security.access import AccessAction, AccessContext


class ChatModel(Protocol):
    @property
    def model_metadata(self) -> ModelMetadata: ...

    def generate_response(
        self,
        messages: Sequence[Mapping[str, str]],
        temperature: float = 0.7,
    ) -> str: ...


class RenderedPromptPort(Protocol):
    prompt_id: str
    version: str
    role: str
    content: str
    sha256: str

    def as_message(self) -> dict[str, str]: ...


class PromptRendererPort(Protocol):
    def render(
        self,
        prompt_id: str,
        variables: dict[str, Any] | None = None,
    ) -> RenderedPromptPort: ...

    def render_from_context(
        self,
        prompt_id: str,
        context: dict[str, Any],
    ) -> RenderedPromptPort: ...


class MemoryRepository(Protocol):
    def save_source_transcript(self, title: str, content: str, mode: str) -> str: ...

    def save_core_value(
        self,
        title: str,
        content: str,
        source_ref: str | None = None,
    ) -> bool: ...

    def save_story(
        self,
        title: str,
        content: str,
        source_ref: str | None = None,
    ) -> bool: ...

    def read_master_identity(self) -> str: ...

    def save_master_identity(self, content: str) -> bool: ...


class IdentitySnapshotRepository(Protocol):
    def create_identity_snapshot(self, snapshot: IdentitySnapshot) -> None: ...

    def get_identity_snapshot(self, snapshot_id: str) -> IdentitySnapshot | None: ...

    def get_active_identity_snapshot(self) -> IdentitySnapshot | None: ...

    def list_identity_snapshots(
        self,
        status: IdentitySnapshotStatus | None = None,
        limit: int = 20,
    ) -> list[IdentitySnapshot]: ...

    def review_identity_snapshot(
        self,
        snapshot_id: str,
        status: IdentitySnapshotStatus,
        reviewed_by: str,
        review_note: str | None = None,
    ) -> IdentitySnapshot: ...


class AccessPolicyPort(Protocol):
    def require(self, action: AccessAction, resource: str, context: AccessContext) -> None: ...


class AssetScannerPort(Protocol):
    def count_notes_and_words(self) -> tuple[int, int]: ...

    def count_audio_duration(self) -> float: ...


class RetrievalGenerationPort(Protocol):
    def build_and_activate(self, documents: list[Any]) -> str: ...


class MemoryRetriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[Any]: ...


class AvatarMemoryContextPort(Protocol):
    def load_level_1_rom(self, now: datetime) -> str: ...

    def load_level_2_personality(self) -> str: ...


class MemoryGapRepositoryPort(Protocol):
    def record_gap(self, query: str, score: float, occurred_at: datetime) -> None: ...


class SyncHistoryRepository(Protocol):
    def save_sync_record(self, metrics: dict[str, float | int | str | None]) -> None: ...

    def list_sync_history(self) -> list[SyncHistoryEntry]: ...


class SpeechToTextPort(Protocol):
    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str: ...
