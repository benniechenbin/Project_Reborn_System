from functools import cached_property
from typing import TYPE_CHECKING, Any

from reborn_core.application.models import ChatMessage, InterviewMode
from reborn_core.application.services import (
    IdentityGovernanceService,
    InterviewService,
    SyncService,
)
from reborn_core.config import Settings

if TYPE_CHECKING:
    from reborn_core.infrastructure.database import (
        MigrationRunner,
        SQLiteAuditRepository,
        SQLiteBackupRecordRepository,
        SQLiteDatabase,
        SQLiteIdentitySnapshotRepository,
        SQLiteSyncHistoryRepository,
        SQLiteTaskRepository,
    )


class Container:
    """显式、惰性地装配可替换的应用依赖。"""

    def __init__(self, app_settings: Settings | None = None) -> None:
        self.settings = app_settings or Settings()

    @cached_property
    def database(self) -> "SQLiteDatabase":
        from reborn_core.infrastructure.database import SQLiteDatabase

        return SQLiteDatabase(app_settings=self.settings)

    @cached_property
    def migration_runner(self) -> "MigrationRunner":
        from reborn_core.infrastructure.database import MigrationRunner

        return MigrationRunner(self.database)

    @cached_property
    def identity_snapshot_repository(self) -> "SQLiteIdentitySnapshotRepository":
        from reborn_core.infrastructure.database import SQLiteIdentitySnapshotRepository

        return SQLiteIdentitySnapshotRepository(self.database)

    @cached_property
    def task_repository(self) -> "SQLiteTaskRepository":
        from reborn_core.infrastructure.database import SQLiteTaskRepository

        return SQLiteTaskRepository(self.database)

    @cached_property
    def sync_history_repository(self) -> "SQLiteSyncHistoryRepository":
        from reborn_core.infrastructure.database import SQLiteSyncHistoryRepository

        return SQLiteSyncHistoryRepository(self.database)

    @cached_property
    def backup_record_repository(self) -> "SQLiteBackupRecordRepository":
        from reborn_core.infrastructure.database import SQLiteBackupRecordRepository

        return SQLiteBackupRecordRepository(self.database)

    @cached_property
    def audit_repository(self) -> "SQLiteAuditRepository":
        from reborn_core.infrastructure.database import SQLiteAuditRepository

        return SQLiteAuditRepository(self.database)

    @cached_property
    def access_policy(self):
        from reborn_core.security import AuditedAccessPolicy, LocalOwnerAccessPolicy

        if self.settings.access_policy_backend != "local_owner":
            raise ValueError(
                f"Unsupported access policy adapter: {self.settings.access_policy_backend}"
            )
        return AuditedAccessPolicy(LocalOwnerAccessPolicy(), self.audit_repository)

    @cached_property
    def legacy_activation_policy(self):
        from reborn_core.security import LegacyActivationPolicy

        return LegacyActivationPolicy(self.settings)

    @cached_property
    def task_runner(self):
        from reborn_core.runtime import BackgroundTaskRunner

        return BackgroundTaskRunner(
            repository=self.task_repository,
            max_workers=self.settings.task_worker_threads,
        )

    @cached_property
    def llm_router(self):
        from reborn_core.infrastructure.brain.llm_router import LLMRouter

        return LLMRouter(app_settings=self.settings)

    @cached_property
    def prompt_registry(self):
        from reborn_core.domains.brain.prompt_registry import get_prompt_registry

        return get_prompt_registry()

    @cached_property
    def memory_writer(self):
        from reborn_core.domains.memory.memory_writer import MemoryWriter

        return MemoryWriter(app_settings=self.settings)

    @cached_property
    def interview_service(self) -> InterviewService:
        return InterviewService(
            self.llm_router,
            self.memory_writer,
            self.identity_snapshot_repository,
            app_settings=self.settings,
            prompt_registry=self.prompt_registry,
        )

    @cached_property
    def identity_governance_service(self) -> IdentityGovernanceService:
        return IdentityGovernanceService(
            self.identity_snapshot_repository,
            self.memory_writer,
            self.access_policy,
            llm_router_factory=lambda: self.llm_router,
            app_settings=self.settings,
            prompt_registry=self.prompt_registry,
        )

    @cached_property
    def retrieval_generations(self):
        from reborn_core.infrastructure.retrieval import RetrievalGenerationManager

        def make_provider(path):
            from reborn_core.domains.memory.vector_store import QdrantDBProvider

            return QdrantDBProvider(app_settings=self.settings, vector_db_path=path)

        return RetrievalGenerationManager(
            root=self.settings.resolved_vector_db_path,
            provider_factory=make_provider,
            retention=self.settings.retrieval_generation_retention,
        )

    @cached_property
    def rag_engine(self):
        from reborn_core.domains.brain.rag_engine import RAGEngine

        return RAGEngine(
            app_settings=self.settings,
            llm_router=self.llm_router,
            vector_db=self.retrieval_generations,
        )

    @cached_property
    def stt_engine(self):
        from reborn_core.infrastructure.brain.stt_engine import STTEngine

        return STTEngine(app_settings=self.settings)

    @cached_property
    def sync_service(self) -> SyncService:
        from reborn_core.infrastructure.knowledge import AssetScanner, load_processed_knowledge

        obsidian_path = self.settings.active_obsidian_path or (
            self.settings.base_dir / "data" / "memories"
        )
        audio_path = self.settings.active_audio_path or (self.settings.base_dir / "data" / "audio")
        scanner = AssetScanner(
            obsidian_path=obsidian_path,
            audio_path=audio_path,
            target_folders=self.settings.memory_index_folders,
        )
        return SyncService(
            scanner=scanner,
            knowledge_loader=lambda: load_processed_knowledge(
                vault_path=obsidian_path,
                target_folders=self.settings.memory_index_folders,
            ),
            generation_store=self.retrieval_generations,
            history_repository=self.sync_history_repository,
        )

    @cached_property
    def backup_service(self):
        from reborn_core.infrastructure.backup import BackupService

        return BackupService(self.settings, self.backup_record_repository, self.access_policy)

    # 这些方法会特意在后台工作线程中解析并加载重量级惰性依赖。
    def run_sync(self):
        return self.sync_service.execute_full_sync()

    def run_interview(
        self,
        chat_history: list[ChatMessage],
        mode: InterviewMode,
        custom_title: str | None = None,
    ):
        return self.interview_service.process_interview(chat_history, mode, custom_title)

    def process_voice_capture(self, audio_bytes: bytes):
        transcript = self.stt_engine.transcribe_audio_bytes(audio_bytes)
        if not transcript:
            raise ValueError(
                "没有识别到有效语音，请确认录音时长、麦克风权限以及 FunASR 本地模型缓存是否可用。"
            )
        result = self.interview_service.process_interview(
            [{"role": "user", "content": f"Voice journal:\n{transcript}"}],
            InterviewMode.LIFE_STORY,
        )
        return {"transcript": transcript, "interview": result}

    def warm_rag_engine(self) -> Any:
        return self.rag_engine

    def generate_chat(self, messages: list[dict[str, str]]) -> str:
        return self.llm_router.generate_response(messages)

    def render_builder_prompt_message(self, prompt_id: str) -> dict[str, str]:
        context = {
            "creator_name": self.settings.creator_name,
            "child_nickname": self.settings.child_nickname,
        }
        return self.prompt_registry.render_from_context(prompt_id, context).as_message()

    def generate_avatar_response(
        self,
        query: str,
        chat_history: list[dict[str, str]],
    ):
        return self.rag_engine.generate_avatar_response(query, chat_history)

    def run_backup(self):
        return self.backup_service.create_backup()

    def run_recovery_drill(self, path: str):
        from pathlib import Path

        return self.backup_service.run_recovery_drill(Path(path))
