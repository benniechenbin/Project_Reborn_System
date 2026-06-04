import json
import uuid
import hashlib

from reborn_core.observability import logger
from reborn_core.application.models import (
    IdentitySnapshot,
    IdentitySnapshotStatus,
    ModelMetadata,  # 👈 新增
    PromptMetadata,  # 👈 新增
)
from reborn_core.application.ports import (
    AccessPolicyPort,
    IdentitySnapshotRepository,
    MemoryRepository,
)
from reborn_core.security import AccessAction, AccessContext


class IdentityGovernanceService:
    """通过人工审核决定是否晋升生成的身份快照。"""

    def __init__(
        self,
        snapshots: IdentitySnapshotRepository,
        memory: MemoryRepository,
        access_policy: AccessPolicyPort,
        llm_router=None,
    ) -> None:
        self.snapshots = snapshots
        self.memory = memory
        self.access_policy = access_policy
        self.llm_router = llm_router

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
        if not self.llm_router:
            logger.error("❌ 未注入 llm_router，无法执行夜间反思")
            return None

        logger.info(f"🌙 开始执行夜间反思，分析 {len(chat_logs)} 条对话...")

        prompt = (
            "请分析以下聊天记录，提取出关于孩子的最新兴趣、重要事件，"
            "或者总结出作为父亲下次沟通时需要注意的规则。\n"
            f"聊天记录：{json.dumps(chat_logs, ensure_ascii=False)}"
        )

        # 调用大模型
        try:
            reflection_result = self.llm_router.generate_response(
                [{"role": "user", "content": prompt}]
            )
        except Exception as e:
            logger.error(f"夜间反思大模型调用失败: {e}")
            return None

        logger.debug(f"🧠 大模型反思提取完毕: {reflection_result}")

        try:
            # 1. 计算双重防篡改哈希
            content_hash = hashlib.sha256(reflection_result.encode("utf-8")).hexdigest()
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

            # 2. 获取模型元数据 (ModelMetadata)
            # 因为 llm_router 可能在类型检查时被认为是 Any，所以这里我们做一层安全适配
            model_meta = getattr(self.llm_router, "model_metadata", None)
            if not isinstance(model_meta, ModelMetadata):
                # 兜底：如果 router 没有按协议返回 ModelMetadata，我们手动拼装一个
                model_meta = ModelMetadata(
                    provider="llm_router",
                    model_name=getattr(self.llm_router, "model_name", "unknown"),
                )

            # 3. 构造提示词元数据 (PromptMetadata) - 完美契合你 models.py 的定义！
            prompt_meta = PromptMetadata(
                prompt_id="nightly_reflection_system", version="1.0.0", sha256=prompt_hash
            )

            # 4. 彻底点亮 DDD 实体！
            new_snapshot = IdentitySnapshot(
                snapshot_id=str(uuid.uuid4()),
                content=reflection_result,
                content_sha256=content_hash,
                source_ids=("nightly_reflection",),  # 👈 修复 1：安全的 Tuple
                model=model_meta,  # 👈 修复 2：ModelMetadata 实例
                prompt=prompt_meta,  # 👈 修复 3：PromptMetadata 实例
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
