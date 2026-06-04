from collections.abc import Callable
from typing import Any

from reborn_core.application.models import SyncMetrics
from reborn_core.application.ports import (
    AssetScannerPort,
    RetrievalGenerationPort,
    SyncHistoryRepository,
)
from reborn_core.observability import logger


class SyncService:
    """构建新的检索索引代次，并仅在校验通过后将其激活。"""

    def __init__(
        self,
        scanner: AssetScannerPort,
        knowledge_loader: Callable[[], list[Any]],
        generation_store: RetrievalGenerationPort,
        history_repository: SyncHistoryRepository,
    ) -> None:
        self.scanner = scanner
        self.knowledge_loader = knowledge_loader
        self.generation_store = generation_store
        self.history_repository = history_repository

    def execute_full_sync(self) -> SyncMetrics:
        logger.info("Starting full memory sync")
        notes_count, word_count = self.scanner.count_notes_and_words()
        documents = self.knowledge_loader()
        generation_id = self.generation_store.build_and_activate(documents) if documents else None
        if not documents:
            logger.warning("No documents found; the active retrieval generation is unchanged")

        metrics = SyncMetrics(
            audio_duration=self.scanner.count_audio_duration(),
            notes_count=notes_count,
            word_count=word_count,
            generation_id=generation_id,
        )
        self.history_repository.save_sync_record(metrics.as_dict())
        return metrics
