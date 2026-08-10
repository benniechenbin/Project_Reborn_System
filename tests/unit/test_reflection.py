import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from reborn_core.application import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    SensitivityLevel,
    SourceArtifact,
    SourceArtifactType,
)
from reborn_core.application.models import ModelMetadata, PromptMetadata
from reborn_core.application.services import ReflectionService
from reborn_core.infrastructure.memory import LocalReflectionSourceStorage


class StubLLM:
    def __init__(self, response: str = "reflective candidate") -> None:
        self.response = response
        self.calls = 0

    @property
    def model_metadata(self) -> ModelMetadata:
        return ModelMetadata("stub", "reflection-model")

    def generate_response(self, messages, temperature=0.7):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StubSnapshots:
    def __init__(self, active: IdentitySnapshot | None) -> None:
        self.active = active
        self.items: dict[str, IdentitySnapshot] = {}
        if active is not None:
            self.items[active.snapshot_id] = active

    def create_identity_snapshot(self, snapshot):
        self.items[snapshot.snapshot_id] = snapshot

    def get_identity_snapshot(self, snapshot_id):
        return self.items.get(snapshot_id)

    def get_active_identity_snapshot(self):
        return self.active

    def list_identity_snapshots(self, status=None, limit=20):
        return list(self.items.values())[:limit]

    def review_identity_snapshot(self, snapshot_id, status, reviewed_by, review_note=None):
        raise NotImplementedError


class StubArtifacts:
    def __init__(self, *, fail_create: bool = False) -> None:
        self.items: dict[str, SourceArtifact] = {}
        self.fail_create = fail_create

    def create_source_artifact(self, artifact):
        if self.fail_create:
            raise RuntimeError("repository failed")
        self.items[artifact.artifact_id] = artifact

    def get_source_artifact(self, artifact_id):
        return self.items.get(artifact_id)

    def list_source_artifacts(self, artifact_type=None, limit=20):
        return list(self.items.values())[:limit]


def active_snapshot(snapshot_id: str = "approved-1") -> IdentitySnapshot:
    return IdentitySnapshot(
        snapshot_id=snapshot_id,
        content="stable values",
        content_sha256=hashlib.sha256(b"stable values").hexdigest(),
        source_ids=("source-1",),
        model=ModelMetadata("owner", "human-review"),
        prompt=PromptMetadata("identity", "1", "a" * 64),
        generation_params={},
        status=IdentitySnapshotStatus.APPROVED,
        active=True,
    )


def make_service(
    tmp_path,
    prompt_context,
    prompt_renderer,
    *,
    snapshots=None,
    artifacts=None,
    llm=None,
):
    snapshots = snapshots or StubSnapshots(active_snapshot())
    artifacts = artifacts or StubArtifacts()
    storage = LocalReflectionSourceStorage(tmp_path, "SourceArtifacts")
    service = ReflectionService(
        snapshots=snapshots,
        source_artifacts=artifacts,
        source_storage=storage,
        prompt_context=prompt_context,
        prompt_renderer=prompt_renderer,
        llm_router=llm or StubLLM(),
        clock=lambda: datetime(2026, 8, 10, tzinfo=UTC),
    )
    return service, snapshots, artifacts, storage


def test_prepare_source_requires_authorization(tmp_path, prompt_context, prompt_renderer):
    service, _, artifacts, _ = make_service(tmp_path, prompt_context, prompt_renderer)

    with pytest.raises(ValueError, match="授权"):
        service.prepare_source(
            [{"role": "user", "content": "private"}],
            consent_given=False,
        )

    assert artifacts.items == {}
    assert not (tmp_path / "SourceArtifacts").exists()


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "system", "content": "hidden"}],
        [{"role": "user", "content": " "}],
        [{"role": "user", "content": "ok", "extra": "no"}],
    ],
)
def test_prepare_source_rejects_invalid_messages(
    tmp_path,
    prompt_context,
    prompt_renderer,
    messages,
):
    service, _, artifacts, _ = make_service(tmp_path, prompt_context, prompt_renderer)

    with pytest.raises(ValueError):
        service.prepare_source(messages, consent_given=True)

    assert artifacts.items == {}


def test_prepare_source_requires_active_approved_snapshot(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    snapshots = StubSnapshots(None)
    service, _, artifacts, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        snapshots=snapshots,
    )

    with pytest.raises(ValueError, match="active approved"):
        service.prepare_source(
            [{"role": "user", "content": "private"}],
            consent_given=True,
        )

    assert artifacts.items == {}


def test_prepare_source_records_exact_file_integrity_and_parent(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    service, _, artifacts, storage = make_service(tmp_path, prompt_context, prompt_renderer)

    artifact = service.prepare_source(
        [
            {"role": "user", "content": "  astronomy  "},
            {"role": "assistant", "content": "Tell me more."},
        ],
        consent_given=True,
    )

    payload = storage.read(artifact.storage_path)
    document = json.loads(payload)
    assert artifact.artifact_type is SourceArtifactType.REFLECTION_TRANSCRIPT
    assert artifact.authorization_purpose == "identity_reflection"
    assert artifact.authorized_target == "nightly_reflection"
    assert artifact.sensitivity_level is SensitivityLevel.HIGH
    assert artifact.file_size_bytes == len(payload)
    assert artifact.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert artifact.metadata == {
        "schema_version": 1,
        "media_type": "application/json",
        "message_count": 2,
        "parent_snapshot_id": "approved-1",
    }
    assert document["messages"][0]["content"] == "astronomy"
    assert artifacts.items[artifact.artifact_id] == artifact


def test_prepare_source_removes_file_when_repository_write_fails(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    artifacts = StubArtifacts(fail_create=True)
    service, _, _, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        artifacts=artifacts,
    )

    with pytest.raises(RuntimeError, match="repository failed"):
        service.prepare_source(
            [{"role": "user", "content": "private"}],
            consent_given=True,
        )

    assert list(tmp_path.rglob("*.json")) == []


def test_run_creates_traceable_pending_snapshot(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    llm = StubLLM()
    service, snapshots, _, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )
    artifact = service.prepare_source(
        [{"role": "user", "content": "I like astronomy."}],
        consent_given=True,
    )

    snapshot = service.run(artifact.artifact_id)

    assert llm.calls == 1
    assert snapshot.status is IdentitySnapshotStatus.PENDING_REVIEW
    assert snapshot.parent_snapshot_id == "approved-1"
    assert snapshot.source_ids == (artifact.artifact_id,)
    assert snapshot.prompt.prompt_id == "nightly_reflection_system"
    assert snapshots.items[snapshot.snapshot_id] == snapshot


def test_run_rejects_missing_artifact_before_llm(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    llm = StubLLM()
    service, snapshots, _, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )

    with pytest.raises(LookupError, match="not found"):
        service.run("missing")

    assert llm.calls == 0
    assert len(snapshots.items) == 1


def test_run_rejects_source_path_outside_archive_root(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    llm = StubLLM()
    service, snapshots, artifacts, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )
    artifact = service.prepare_source(
        [{"role": "user", "content": "private"}],
        consent_given=True,
    )
    artifacts.items[artifact.artifact_id] = replace(
        artifact,
        storage_path="../outside.json",
    )

    with pytest.raises(ValueError, match="escaped"):
        service.run(artifact.artifact_id)

    assert llm.calls == 0
    assert len(snapshots.items) == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda artifact: replace(
                artifact,
                authorization_purpose="voice_model_training",
            ),
            "identity reflection",
        ),
        (
            lambda artifact: replace(
                artifact,
                authorized_target="other",
            ),
            "nightly reflection",
        ),
        (
            lambda artifact: replace(
                artifact,
                artifact_type=SourceArtifactType.AUDIO_DATASET,
            ),
            "not a reflection transcript",
        ),
    ],
)
def test_run_rejects_noncompliant_artifact(
    tmp_path,
    prompt_context,
    prompt_renderer,
    change,
    message,
):
    llm = StubLLM()
    service, snapshots, artifacts, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )
    artifact = service.prepare_source(
        [{"role": "user", "content": "private"}],
        consent_given=True,
    )
    artifacts.items[artifact.artifact_id] = change(artifact)

    with pytest.raises(ValueError, match=message):
        service.run(artifact.artifact_id)

    assert llm.calls == 0
    assert len(snapshots.items) == 1


def test_run_rejects_tampered_source_before_llm(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    llm = StubLLM()
    service, snapshots, _, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )
    artifact = service.prepare_source(
        [{"role": "user", "content": "private"}],
        consent_given=True,
    )
    (tmp_path / artifact.storage_path).write_bytes(b"tampered")

    with pytest.raises(ValueError, match="size|hash"):
        service.run(artifact.artifact_id)

    assert llm.calls == 0
    assert len(snapshots.items) == 1


def test_run_rejects_source_when_parent_is_no_longer_active(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    llm = StubLLM()
    service, snapshots, _, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )
    artifact = service.prepare_source(
        [{"role": "user", "content": "private"}],
        consent_given=True,
    )
    snapshots.active = active_snapshot("approved-2")

    with pytest.raises(ValueError, match="no longer active"):
        service.run(artifact.artifact_id)

    assert llm.calls == 0
    assert len(snapshots.items) == 1


def test_run_propagates_llm_failure_without_creating_candidate(
    tmp_path,
    prompt_context,
    prompt_renderer,
):
    llm = StubLLM(RuntimeError("llm unavailable"))
    service, snapshots, _, _ = make_service(
        tmp_path,
        prompt_context,
        prompt_renderer,
        llm=llm,
    )
    artifact = service.prepare_source(
        [{"role": "user", "content": "private"}],
        consent_given=True,
    )

    with pytest.raises(RuntimeError, match="llm unavailable"):
        service.run(artifact.artifact_id)

    assert len(snapshots.items) == 1
