import json
from dataclasses import dataclass
from pathlib import Path

from reborn_core.domains import LegacyActivationMode
from reborn_core.config import Settings


@dataclass(frozen=True, slots=True)
class LegacyActivationStatus:
    active: bool
    mode: LegacyActivationMode
    reason: str
    authorized_by: str | None = None
    evidence_reference: str | None = None


class LegacyActivationPolicy:
    """评估明确的数字遗产激活规则，但不负责提供身份认证。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self) -> LegacyActivationStatus:
        mode = self.settings.legacy_activation_mode
        if mode is LegacyActivationMode.ACTIVATED:
            return LegacyActivationStatus(True, mode, "Explicitly activated by configuration")
        if mode is LegacyActivationMode.OWNER_ONLY:
            return LegacyActivationStatus(False, mode, "Owner-only mode; legacy access is disabled")
        return self._evaluate_activation_file(self.settings.resolved_legacy_activation_file)

    def _evaluate_activation_file(self, path: Path) -> LegacyActivationStatus:
        if not path.exists():
            return LegacyActivationStatus(
                False, LegacyActivationMode.ACTIVATION_FILE, "File missing"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return LegacyActivationStatus(
                False,
                LegacyActivationMode.ACTIVATION_FILE,
                "Activation file is unreadable",
            )

        required = (
            payload.get("activated") is True
            and bool(payload.get("authorized_by"))
            and bool(payload.get("approved_at"))
            and bool(payload.get("evidence_reference"))
        )
        return LegacyActivationStatus(
            active=required,
            mode=LegacyActivationMode.ACTIVATION_FILE,
            reason="Activation evidence accepted" if required else "Activation evidence incomplete",
            authorized_by=payload.get("authorized_by"),
            evidence_reference=payload.get("evidence_reference"),
        )
