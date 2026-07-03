import json
import uuid
import hashlib
from collections.abc import Callable
from typing import Any

from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,
    PromptMetadata,
)
from reborn_core.application.ports import (
    AccessPolicyPort,
    IdentitySnapshotRepository,
    MemoryRepository,
)
from reborn_core.config import Settings, get_settings
from reborn_core.domains.brain.prompt_registry import (
    PromptRegistry,
    RenderedPrompt,
    get_prompt_registry,
)
from reborn_core.observability import logger
from reborn_core.security import AccessAction, AccessContext

NIGHTLY_REFLECTION_PROMPT_ID = "nightly_reflection_system"


class IdentityGovernanceService:
    """通过人工审核决定是否晋升生成的身份快照。"""

    def __init__(
        self,
        snapshots: IdentitySnapshotRepository,
        memory: MemoryRepository,
        access_policy: AccessPolicyPort,
        llm_router=None,
        llm_router_factory: Callable[[], Any] | None = None,
        app_settings: Settings | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self.snapshots = snapshots
        self.memory = memory
        self.access_policy = access_policy
        self.llm_router = llm_router
        self.llm_router_factory = llm_router_factory
        self.settings = app_settings or get_settings()
        self.prompt_registry = prompt_registry or get_prompt_registry()

    def list_pending(self, limit: int = 20) -> list[IdentitySnapshot]:
        return self.snapshots.list_identity_snapshots(IdentitySnapshotStatus.PENDING_REVIEW, limit)

    def approve(
        self,
        snapshot_id: str,
        review_note: str | None = None,
        context: AccessContext | None = None,
    ) -> IdentitySnapshot:
        context = context or AccessContext()
        self.access_policy.require(AccessAction.APPROVE_IDENTITY, snapshot_id, context)
        snapshot = self._pending(snapshot_id)
        if not self.memory.save_master_identity(snapshot.content):
            raise RuntimeError("Could not promote the approved identity snapshot")
        return self.snapshots.review_identity_snapshot(
            snapshot_id,
            IdentitySnapshotStatus.APPROVED,
            reviewed_by=context.actor_id,
            review_note=review_note,
        )

    def reject(
        self,
        snapshot_id: str,
        review_note: str | None = None,
        context: AccessContext | None = None,
    ) -> IdentitySnapshot:
        context = context or AccessContext()
        self.access_policy.require(AccessAction.APPROVE_IDENTITY, snapshot_id, context)
        self._pending(snapshot_id)
        return self.snapshots.review_identity_snapshot(
            snapshot_id,
            IdentitySnapshotStatus.REJECTED,
            reviewed_by=context.actor_id,
            review_note=review_note,
        )

    def _pending(self, snapshot_id: str) -> IdentitySnapshot:
        snapshot = self.snapshots.get_identity_snapshot(snapshot_id)
        if snapshot is None:
            raise LookupError(f"Identity snapshot not found: {snapshot_id}")
        if snapshot.status is not IdentitySnapshotStatus.PENDING_REVIEW:
            raise ValueError(f"Identity snapshot is already {snapshot.status.value}")
        return snapshot

    def run_nightly_reflection(self, chat_logs: list[dict[str, str]]) -> IdentitySnapshot | None:
        """
        🌙 夜间反思守护进程 (Nightly Reflection)
        """
        llm_router = self.llm_router or (
            self.llm_router_factory() if self.llm_router_factory else None
        )
        if not llm_router:
            logger.error("❌ 未注入 llm_router，无法执行夜间反思")
            return None

        logger.info(f"🌙 开始执行夜间反思，分析 {len(chat_logs)} 条对话...")

        system_prompt = self._render_prompt(NIGHTLY_REFLECTION_PROMPT_ID)
        user_prompt = (
            "请分析以下聊天记录，只提取有助于安全陪伴和长期沟通的最小必要信息。\n"
            f"聊天记录：{json.dumps(chat_logs, ensure_ascii=False)}"
        )

        # 调用大模型
        try:
            reflection_result = llm_router.generate_response(
                [system_prompt.as_message(), {"role": "user", "content": user_prompt}]
            )
        except Exception as e:
            logger.error(f"夜间反思大模型调用失败: {e}")
            return None

        logger.debug(f"🧠 大模型反思提取完毕: {reflection_result}")

        try:
            # 1. 计算双重防篡改哈希
            content_hash = hashlib.sha256(reflection_result.encode("utf-8")).hexdigest()

            # 2. 获取模型元数据 (ModelMetadata)
            # 因为 llm_router 可能在类型检查时被认为是 Any，所以这里我们做一层安全适配
            model_meta = getattr(llm_router, "model_metadata", None)
            if not isinstance(model_meta, ModelMetadata):
                # 兜底：如果 router 没有按协议返回 ModelMetadata，我们手动拼装一个
                model_meta = ModelMetadata(
                    provider="llm_router",
                    model_name=getattr(llm_router, "model_name", "unknown"),
                )

            # 3. 构造提示词元数据 (PromptMetadata) - 完美契合你 models.py 的定义！
            prompt_meta = PromptMetadata(
                prompt_id=system_prompt.prompt_id,
                version=system_prompt.version,
                sha256=system_prompt.sha256,
            )

            # 4. 彻底点亮 DDD 实体！
            new_snapshot = IdentitySnapshot(
                snapshot_id=str(uuid.uuid4()),
                content=reflection_result,
                content_sha256=content_hash,
                source_ids=("nightly_reflection",),
                model=model_meta,
                prompt=prompt_meta,
                generation_params={"temperature": 0.7, "max_tokens": 1500},
                status=IdentitySnapshotStatus.PENDING_REVIEW,
                # created_at 由 dataclass default_factory 自动生成，优雅留空！
            )

            self.snapshots.create_identity_snapshot(new_snapshot)

            logger.info(
                f"✅ 夜间反思结束，新记忆快照 (ID: {new_snapshot.snapshot_id}) 已安全送入【审批隔离区】。"
            )

            return new_snapshot

        except Exception as e:
            logger.error(f"❌ 严重错误：新记忆生成成功，但持久化到数据库失败: {e}")
            raise RuntimeError(f"夜间反思持久化失败: {e}") from e

    def _render_prompt(self, prompt_id: str) -> RenderedPrompt:
        context = {
            "creator_name": self.settings.creator_name,
            "child_nickname": self.settings.child_nickname,
        }
        return self.prompt_registry.render_from_context(prompt_id, context)
