import hashlib
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from reborn_core.application.models import (
    ChatMessage,
    IdentitySnapshot,
    IdentitySnapshotStatus,
    InterviewMode,
    InterviewResult,
    ModelMetadata,
    PromptContext,
    PromptMetadata,
)
from reborn_core.application.ports import (
    ChatModel,
    IdentitySnapshotRepository,
    MemoryRepository,
    PromptRendererPort,
    RenderedPromptPort,
)
from reborn_core.observability import logger

IDENTITY_PROMPT_ID = "identity_consolidation"
MEMORY_EXTRACTION_PROMPT_ID = "memory_extraction"
STORY_EXTRACTION_PROMPT_ID = "story_extraction"


class InterviewService:
    """提炼记忆并创建可追溯的待审核身份快照。"""

    def __init__(
        self,
        llm_router: ChatModel,
        memory_writer: MemoryRepository,
        identity_snapshots: IdentitySnapshotRepository,
        prompt_context: PromptContext,
        prompt_renderer: PromptRendererPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.llm = llm_router
        self.memory = memory_writer
        self.identity_snapshots = identity_snapshots
        self.prompt_context = prompt_context
        self.prompt_renderer = prompt_renderer
        self.clock = clock or (lambda: datetime.now(UTC))

    def process_interview(
        self,
        chat_history: Sequence[ChatMessage],
        mode: InterviewMode,
        custom_title: str | None = None,
    ) -> InterviewResult:
        transcript = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in chat_history
            if message["role"] != "system" and message["content"].strip()
        )
        if not transcript:
            raise ValueError("Interview content is empty")

        title = (
            custom_title.strip() if custom_title and custom_title.strip() else self._default_title()
        )
        source_ref = self.memory.save_source_transcript(title, transcript, mode.value)

        extraction_prompt_id = (
            MEMORY_EXTRACTION_PROMPT_ID
            if mode is InterviewMode.CORE_VALUES
            else STORY_EXTRACTION_PROMPT_ID
        )
        extraction_prompt = self._render_prompt(extraction_prompt_id)
        insight = self.llm.generate_response(
            [
                extraction_prompt.as_message(),
                {"role": "user", "content": f"Process this transcript:\n{transcript}"},
            ]
        )
        saved = (
            self.memory.save_core_value(title, insight, source_ref=source_ref)
            if mode is InterviewMode.CORE_VALUES
            else self.memory.save_story(title, insight, source_ref=source_ref)
        )
        if not saved:
            raise RuntimeError("Could not persist the derived memory")

        identity_prompt = self._render_prompt(IDENTITY_PROMPT_ID)
        identity_content = self.llm.generate_response(
            [
                identity_prompt.as_message(),
                {
                    "role": "user",
                    "content": (
                        f"Existing approved identity:\n{self.memory.read_master_identity()}"
                        f"\n\nNew derived memory:\n{insight}"
                    ),
                },
            ]
        )
        active = self.identity_snapshots.get_active_identity_snapshot()
        model = getattr(
            self.llm,
            "model_metadata",
            ModelMetadata(provider="unknown", model_name="unknown"),
        )
        snapshot = IdentitySnapshot(
            snapshot_id=uuid.uuid4().hex,
            parent_snapshot_id=active.snapshot_id if active else None,
            content=identity_content,
            content_sha256=_sha256(identity_content),
            source_ids=(source_ref,),
            model=model,
            prompt=PromptMetadata(
                prompt_id=identity_prompt.prompt_id,
                version=identity_prompt.version,
                sha256=identity_prompt.sha256,
            ),
            generation_params={
                "temperature": 0.7,
                "extraction_prompt": {
                    "prompt_id": extraction_prompt.prompt_id,
                    "version": extraction_prompt.version,
                    "sha256": extraction_prompt.sha256,
                },
            },
        )
        self.identity_snapshots.create_identity_snapshot(snapshot)
        logger.info("Created pending identity snapshot {}", snapshot.snapshot_id)

        return InterviewResult(
            title=title,
            mode=mode,
            source_ref=source_ref,
            insight=insight,
            identity_snapshot=identity_content,
            identity_snapshot_id=snapshot.snapshot_id,
            identity_status=IdentitySnapshotStatus.PENDING_REVIEW,
            completed_at=self.clock(),
        )

    def process_and_save_interview(
        self,
        chat_history: Sequence[ChatMessage],
        interview_mode: str,
        custom_title: str | None = None,
    ) -> tuple[bool, str]:
        try:
            result = self.process_interview(
                chat_history=chat_history,
                mode=InterviewMode.from_legacy_label(interview_mode),
                custom_title=custom_title,
            )
            return True, result.insight
        except Exception as exc:
            logger.exception("Interview processing failed")
            return False, str(exc)

    def _default_title(self) -> str:
        return f"memory_{self.clock().strftime('%m%d_%H%M%S')}"

    def _render_prompt(self, prompt_id: str) -> RenderedPromptPort:
        return self.prompt_renderer.render_from_context(prompt_id, self.prompt_context.as_dict())


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
