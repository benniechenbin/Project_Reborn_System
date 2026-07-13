import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from reborn_core.observability import logger


class JsonMemoryGapRepository:
    """Persists low-confidence avatar queries as a bounded JSON log."""

    def __init__(
        self,
        path: Path,
        max_entries: int = 100,
        lock: Any | None = None,
    ) -> None:
        self.path = path
        self.max_entries = max_entries
        self._lock = lock or threading.Lock()

    def record_gap(self, query: str, score: float, occurred_at: datetime) -> None:
        try:
            gap_entry = {
                "query": query,
                "score": score,
                "timestamp": occurred_at.strftime("%Y-%m-%d %H:%M:%S"),
            }

            with self._lock:
                gaps = self._load()
                gaps.append(gap_entry)
                gaps = gaps[-self.max_entries :]
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
                try:
                    temp_path.write_text(
                        json.dumps(gaps, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    os.replace(temp_path, self.path)
                finally:
                    if temp_path.exists():
                        temp_path.unlink()
            logger.warning("发现记忆盲区，已记录查询: {} (Score: {})", query, score)
        except Exception as exc:
            logger.error("Failed to record memory gap: {}", exc)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, list) else []
        except json.JSONDecodeError as exc:
            logger.warning("Memory gaps log file corrupted, resetting: {}", exc)
            return []
        except OSError as exc:
            logger.warning("Could not read memory gaps log file: {}", exc)
            return []
