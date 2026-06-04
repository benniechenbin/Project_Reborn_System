from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class AccessAction(StrEnum):
    READ = "read"
    WRITE = "write"
    APPROVE_IDENTITY = "approve_identity"
    BACKUP = "backup"
    RESTORE = "restore"
    ACTIVATE_LEGACY = "activate_legacy"


@dataclass(frozen=True, slots=True)
class AccessContext:
    actor_id: str = "local-owner"
    attributes: dict[str, str] = field(default_factory=dict)


class AccessDeniedError(PermissionError):
    pass


class AccessPolicy(Protocol):
    def require(self, action: AccessAction, resource: str, context: AccessContext) -> None: ...


class LocalOwnerAccessPolicy:
    """单用户访问策略适配器，未来可替换为带身份认证的策略。"""

    def require(self, action: AccessAction, resource: str, context: AccessContext) -> None:
        if context.actor_id != "local-owner":
            raise AccessDeniedError(f"{context.actor_id} cannot {action.value} {resource}")


class AuditRepository(Protocol):
    def append_audit_event(
        self,
        action: str,
        resource: str,
        actor_id: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None: ...


class AuditedAccessPolicy:
    def __init__(self, delegate: AccessPolicy, audit_repository: AuditRepository) -> None:
        self.delegate = delegate
        self.audit_repository = audit_repository

    def require(self, action: AccessAction, resource: str, context: AccessContext) -> None:
        try:
            self.delegate.require(action, resource, context)
        except AccessDeniedError:
            self.audit_repository.append_audit_event(
                action.value, resource, context.actor_id, "denied"
            )
            raise
        self.audit_repository.append_audit_event(
            action.value, resource, context.actor_id, "allowed"
        )
