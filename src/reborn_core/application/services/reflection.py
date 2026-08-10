import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from reborn_core.application.models import (
    ChatMessage,
    IdentitySnapshot,
    IdentitySnapshotStatus,
    PromptContext,
    PromptMetadata,
    SensitivityLevel,
    SourceArtifact,
    SourceArtifactType,
)
from reborn_core.application.ports import (
    ChatModel,
    IdentitySnapshotRepository,
    PromptRendererPort,
    ReflectionSourceStoragePort,
    SourceArtifactRepository,
)

NIGHTLY_REFLECTION_PROMPT_ID = "nightly_reflection_system"
REFLECTION_AUTHORIZATION_PURPOSE = "identity_reflection"
REFLECTION_AUTHORIZED_TARGET = "nightly_reflection"
REFLECTION_SOURCE_SCHEMA_VERSION = 1


class ReflectionService:
    """Archive authorized transcripts and derive traceable identity candidates."""

    def __init__(
        self,
        snapshots: IdentitySnapshotRepository,
        source_artifacts: SourceArtifactRepository,
        source_storage: ReflectionSourceStoragePort,
        prompt_context: PromptContext,
        prompt_renderer: PromptRendererPort,
        llm_router: ChatModel | None = None,
        llm_router_factory: Callable[[], ChatModel] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.snapshots = snapshots
        self.source_artifacts = source_artifacts
        self.source_storage = source_storage
        self.prompt_context = prompt_context
        self.prompt_renderer = prompt_renderer
        self.llm_router = llm_router
        self.llm_router_factory = llm_router_factory
        self.clock = clock or (lambda: datetime.now(UTC))

    def prepare_source(
        self,
        chat_logs: Sequence[Mapping[str, object]],
        *,
        consent_given: bool,
    ) -> SourceArtifact:
        """Persist an authorized transcript before it enters the task queue."""
        if not consent_given:
            raise ValueError("必须明确确认授权后才能归档夜间反思来源")
        active = self._require_active_snapshot()
        messages = _normalize_messages(chat_logs)
        payload = _encode_source(messages)
        artifact_id = uuid.uuid4().hex
        storage_path = self.source_storage.save(artifact_id, payload)
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            artifact_type=SourceArtifactType.REFLECTION_TRANSCRIPT,
            storage_path=storage_path,
            file_size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            authorization_purpose=REFLECTION_AUTHORIZATION_PURPOSE,
            authorized_target=REFLECTION_AUTHORIZED_TARGET,
            sensitivity_level=SensitivityLevel.HIGH,
            captured_at=self.clock().isoformat(),
            metadata={
                "schema_version": REFLECTION_SOURCE_SCHEMA_VERSION,
                "media_type": "application/json",
                "message_count": len(messages),
                "parent_snapshot_id": active.snapshot_id,
            },
        )
        try:
            self.source_artifacts.create_source_artifact(artifact)
        except Exception:
            self.source_storage.delete(storage_path)
            raise
        return artifact

    def run(self, source_artifact_id: str) -> IdentitySnapshot:
        """Validate one archived source and create a pending identity snapshot."""
        artifact = self.source_artifacts.get_source_artifact(source_artifact_id)
        if artifact is None:
            raise LookupError(f"Source artifact not found: {source_artifact_id}")
        parent_snapshot_id, messages = self._validated_source(artifact)
        active = self._require_active_snapshot()
        if active.snapshot_id != parent_snapshot_id:
            raise ValueError(
                "Reflection source is bound to an identity snapshot that is no longer active"
            )

        llm_router = self.llm_router or (
            self.llm_router_factory() if self.llm_router_factory else None
        )
        if llm_router is None:
            raise RuntimeError("No LLM router is configured for nightly reflection")

        system_prompt = self.prompt_renderer.render_from_context(
            NIGHTLY_REFLECTION_PROMPT_ID,
            self.prompt_context.as_dict(),
        )
        user_prompt = (
            "请分析以下聊天记录，只提取有助于安全陪伴和长期沟通的最小必要信息。\n"
            f"聊天记录：{json.dumps(messages, ensure_ascii=False)}"
        )
        reflection_result = llm_router.generate_response(
            [system_prompt.as_message(), {"role": "user", "content": user_prompt}],
            temperature=0.7,
        ).strip()
        if not reflection_result:
            raise RuntimeError("Nightly reflection returned empty content")

        snapshot = IdentitySnapshot(
            snapshot_id=uuid.uuid4().hex,
            parent_snapshot_id=parent_snapshot_id,
            content=reflection_result,
            content_sha256=hashlib.sha256(reflection_result.encode("utf-8")).hexdigest(),
            source_ids=(artifact.artifact_id,),
            model=llm_router.model_metadata,
            prompt=PromptMetadata(
                prompt_id=system_prompt.prompt_id,
                version=system_prompt.version,
                sha256=system_prompt.sha256,
            ),
            generation_params={"temperature": 0.7, "max_tokens": 1500},
            status=IdentitySnapshotStatus.PENDING_REVIEW,
        )
        self.snapshots.create_identity_snapshot(snapshot)
        return snapshot

    def _validated_source(
        self,
        artifact: SourceArtifact,
    ) -> tuple[str, list[ChatMessage]]:
        if artifact.artifact_type is not SourceArtifactType.REFLECTION_TRANSCRIPT:
            raise ValueError("Source artifact is not a reflection transcript")
        if artifact.authorization_purpose != REFLECTION_AUTHORIZATION_PURPOSE:
            raise ValueError("Source artifact is not authorized for identity reflection")
        if artifact.authorized_target != REFLECTION_AUTHORIZED_TARGET:
            raise ValueError("Source artifact is not authorized for nightly reflection")

        metadata = artifact.metadata
        if metadata.get("schema_version") != REFLECTION_SOURCE_SCHEMA_VERSION:
            raise ValueError("Reflection source metadata schema is unsupported")
        if metadata.get("media_type") != "application/json":
            raise ValueError("Reflection source media type is invalid")
        parent_snapshot_id = metadata.get("parent_snapshot_id")
        if not isinstance(parent_snapshot_id, str) or not parent_snapshot_id:
            raise ValueError("Reflection source is missing its parent snapshot binding")

        payload = self.source_storage.read(artifact.storage_path)
        if len(payload) != artifact.file_size_bytes:
            raise ValueError("Reflection source file size does not match its artifact record")
        if hashlib.sha256(payload).hexdigest() != artifact.content_sha256:
            raise ValueError("Reflection source hash does not match its artifact record")
        try:
            document: Any = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Reflection source is not valid UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise ValueError("Reflection source document must be a JSON object")
        if document.get("schema_version") != REFLECTION_SOURCE_SCHEMA_VERSION:
            raise ValueError("Reflection source document schema is unsupported")
        messages = _normalize_messages(document.get("messages"))
        if metadata.get("message_count") != len(messages):
            raise ValueError("Reflection source message count does not match its metadata")
        return parent_snapshot_id, messages

    def _require_active_snapshot(self) -> IdentitySnapshot:
        active = self.snapshots.get_active_identity_snapshot()
        if (
            active is None
            or not active.active
            or active.status is not IdentitySnapshotStatus.APPROVED
        ):
            raise ValueError("Nightly reflection requires an active approved identity snapshot")
        return active


def _encode_source(messages: Sequence[ChatMessage]) -> bytes:
    return json.dumps(
        {
            "schema_version": REFLECTION_SOURCE_SCHEMA_VERSION,
            "messages": list(messages),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _normalize_messages(value: object) -> list[ChatMessage]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("Nightly reflection input must be a JSON message array")
    messages: list[ChatMessage] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
            raise ValueError("Each reflection message must contain only role and content")
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"}:
            raise ValueError("Reflection message role must be user or assistant")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Reflection message content must not be empty")
        messages.append({"role": str(role), "content": content.strip()})
    if not messages:
        raise ValueError("Nightly reflection input must not be empty")
    return messages
