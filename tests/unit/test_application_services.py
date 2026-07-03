from dataclasses import dataclass

import pytest

from reborn_core.application import IdentitySnapshotStatus, InterviewMode
from reborn_core.application.models import ModelMetadata
from reborn_core.application.services import (
    IdentityGovernanceService,
    InterviewService,
    SyncService,
)
from reborn_core.security import LocalOwnerAccessPolicy


class StubLLM:
    def __init__(self):
        self.calls = 0

    @property
    def model_metadata(self):
        return ModelMetadata("stub", "stub-model", "https://example.test")

    def generate_response(self, messages, temperature=0.7):
        self.calls += 1
        return "derived memory" if self.calls == 1 else "pending identity"


class StubMemory:
    def __init__(self):
        self.story = None
        self.identity = "approved identity"
        self.transcript = None

    def save_source_transcript(self, title, content, mode):
        self.transcript = (title, content, mode)
        return "source/interview.md"

    def save_core_value(self, title, content, source_ref=None):
        return True

    def save_story(self, title, content, source_ref=None):
        self.story = (title, content, source_ref)
        return True

    def read_master_identity(self):
        return self.identity

    def save_master_identity(self, content):
        self.identity = content
        return True


class StubSnapshots:
    def __init__(self):
        self.items = {}

    def create_identity_snapshot(self, snapshot):
        self.items[snapshot.snapshot_id] = snapshot

    def get_identity_snapshot(self, snapshot_id):
        return self.items.get(snapshot_id)

    def get_active_identity_snapshot(self):
        return next((item for item in self.items.values() if item.active), None)

    def list_identity_snapshots(self, status=None, limit=20):
        items = list(self.items.values())
        return [item for item in items if status is None or item.status is status][:limit]

    def review_identity_snapshot(self, snapshot_id, status, reviewed_by, review_note=None):
        from dataclasses import replace

        reviewed = replace(
            self.items[snapshot_id],
            status=status,
            reviewed_by=reviewed_by,
            review_note=review_note,
            active=status is IdentitySnapshotStatus.APPROVED,
        )
        self.items[snapshot_id] = reviewed
        return reviewed


def test_interview_creates_pending_identity_without_promoting_it(test_settings):
    llm = StubLLM()
    memory = StubMemory()
    snapshots = StubSnapshots()
    service = InterviewService(llm, memory, snapshots, app_settings=test_settings)

    result = service.process_interview(
        [{"role": "user", "content": "I want to record a journey."}],
        InterviewMode.LIFE_STORY,
        custom_title="Journey",
    )

    assert llm.calls == 2
    assert result.insight == "derived memory"
    assert result.identity_status is IdentitySnapshotStatus.PENDING_REVIEW
    assert memory.identity == "approved identity"
    snapshot = snapshots.get_identity_snapshot(result.identity_snapshot_id)
    assert snapshot.source_ids == ("source/interview.md",)
    assert snapshot.model.model_name == "stub-model"
    assert snapshot.prompt.prompt_id == "identity_consolidation"
    assert snapshot.prompt.version == "2026-07-03.v1"
    assert snapshot.generation_params["extraction_prompt"]["prompt_id"] == "story_extraction"


def test_identity_governance_promotes_only_after_human_approval(test_settings):
    memory = StubMemory()
    snapshots = StubSnapshots()
    result = InterviewService(
        StubLLM(), memory, snapshots, app_settings=test_settings
    ).process_interview(
        [{"role": "user", "content": "A story"}],
        InterviewMode.LIFE_STORY,
    )

    reviewed = IdentityGovernanceService(snapshots, memory, LocalOwnerAccessPolicy()).approve(
        result.identity_snapshot_id, "Reviewed by owner"
    )

    assert reviewed.status is IdentitySnapshotStatus.APPROVED
    assert reviewed.active
    assert memory.identity == "pending identity"


def test_nightly_reflection_uses_registry_prompt_metadata(test_settings):
    llm = StubLLM()
    memory = StubMemory()
    snapshots = StubSnapshots()
    service = IdentityGovernanceService(
        snapshots,
        memory,
        LocalOwnerAccessPolicy(),
        llm_router=llm,
        app_settings=test_settings,
    )

    snapshot = service.run_nightly_reflection([{"role": "user", "content": "I like astronomy."}])

    assert snapshot is not None
    assert snapshot.status is IdentitySnapshotStatus.PENDING_REVIEW
    assert snapshot.prompt.prompt_id == "nightly_reflection_system"
    assert snapshot.prompt.version == "2026-07-03.v1"
    assert len(snapshot.prompt.sha256) == 64


@dataclass
class StubScanner:
    def count_notes_and_words(self):
        return 2, 100

    def count_audio_duration(self):
        return 3.5


class StubGenerations:
    def __init__(self):
        self.documents = None

    def build_and_activate(self, documents):
        self.documents = documents
        return "generation-2"


class StubHistory:
    def __init__(self):
        self.records = []

    def save_sync_record(self, metrics):
        self.records.append(metrics)


def test_sync_keeps_existing_generation_when_no_documents():
    generations = StubGenerations()
    history = StubHistory()
    service = SyncService(StubScanner(), lambda: [], generations, history)

    result = service.execute_full_sync()

    assert generations.documents is None
    assert result.generation_id is None
    assert len(history.records) == 1


def test_sync_records_activated_generation():
    generations = StubGenerations()
    history = StubHistory()
    result = SyncService(StubScanner(), lambda: ["doc"], generations, history).execute_full_sync()

    assert result.generation_id == "generation-2"
    assert history.records[0]["generation_id"] == "generation-2"


def test_interview_rejects_empty_transcript():
    with pytest.raises(ValueError, match="empty"):
        InterviewService(StubLLM(), StubMemory(), StubSnapshots()).process_interview(
            [],
            InterviewMode.CORE_VALUES,
        )
