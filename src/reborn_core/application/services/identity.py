from reborn_core.application.models import IdentitySnapshot, IdentitySnapshotStatus
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
    ) -> None:
        self.snapshots = snapshots
        self.memory = memory
        self.access_policy = access_policy

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
