from functools import cached_property
from typing import TYPE_CHECKING, Any

from reborn_core.application.models import (
    ChatMessage,
    InterviewMode,
    MemoryVaultLayout,
    PromptContext,
)
from reborn_core.application.services import (
    AvatarService,
    IdentityGovernanceService,
    InterviewService,
    SyncService,
)
from reborn_core.config import Settings
from reborn_core.domains import FamilyProfile

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
    def prompt_context(self) -> PromptContext:
        return PromptContext(
            creator_name=self.family_profile.creator.name,
            child_nickname=self.family_profile.child.nickname,
        )

    @cached_property
    def prompt_registry(self):
        from reborn_core.infrastructure.prompting import get_prompt_registry

        return get_prompt_registry()

    @cached_property
    def memory_vault_layout(self) -> MemoryVaultLayout:
        obsidian_root = self.settings.active_obsidian_path or (
            self.settings.base_dir / "data" / "memories"
        )
        return MemoryVaultLayout(
            obsidian_root=obsidian_root,
            core_values_folder=self.settings.core_values_folder,
            stories_folder=self.settings.stories_folder,
            ai_reflections_folder=self.settings.ai_reflections_folder,
            source_artifacts_folder=self.settings.source_artifacts_folder,
            memory_gaps_path=self.settings.resolved_memory_gaps_path,
        )

    @cached_property
    def memory_writer(self):
        from reborn_core.infrastructure.memory import ObsidianMemoryWriter

        return ObsidianMemoryWriter(layout=self.memory_vault_layout)

    @cached_property
    def interview_service(self) -> InterviewService:
        return InterviewService(
            self.llm_router,
            self.memory_writer,
            self.identity_snapshot_repository,
            prompt_context=self.prompt_context,
            prompt_renderer=self.prompt_registry,
        )

    @cached_property
    def identity_governance_service(self) -> IdentityGovernanceService:
        return IdentityGovernanceService(
            self.identity_snapshot_repository,
            self.memory_writer,
            self.access_policy,
            llm_router_factory=lambda: self.llm_router,
            prompt_context=self.prompt_context,
            prompt_renderer=self.prompt_registry,
        )

    @cached_property
    def retrieval_generations(self):
        from reborn_core.infrastructure.retrieval import RetrievalGenerationManager

        def make_provider(path):
            from reborn_core.infrastructure.memory.vector_store import QdrantDBProvider

            return QdrantDBProvider(app_settings=self.settings, vector_db_path=path)

        return RetrievalGenerationManager(
            root=self.settings.resolved_vector_db_path,
            provider_factory=make_provider,
            retention=self.settings.retrieval_generation_retention,
        )

    @cached_property
    def family_profile_repository(self):
        from reborn_core.infrastructure.profile import TomlFamilyProfileRepository

        return TomlFamilyProfileRepository(self.settings.resolved_project_profile_path)

    @cached_property
    def family_profile(self) -> FamilyProfile:
        return self.family_profile_repository.load()

    @cached_property
    def avatar_memory_context(self):
        from reborn_core.infrastructure.memory import ObsidianAvatarMemoryContext

        return ObsidianAvatarMemoryContext(self.memory_vault_layout)

    @cached_property
    def memory_gap_repository(self):
        from reborn_core.infrastructure.memory import JsonMemoryGapRepository

        return JsonMemoryGapRepository(self.memory_vault_layout.memory_gaps_path)

    @cached_property
    def avatar_service(self) -> AvatarService:
        return AvatarService(
            llm_router=self.llm_router,
            memory_retriever=self.retrieval_generations,
            prompt_renderer=self.prompt_registry,
            memory_context=self.avatar_memory_context,
            memory_gaps=self.memory_gap_repository,
            profile=self.family_profile,
        )

    @cached_property
    def rag_engine(self) -> AvatarService:
        return self.avatar_service

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
            "creator_name": self.prompt_context.creator_name,
            "child_nickname": self.prompt_context.child_nickname,
        }
        return self.prompt_registry.render_from_context(prompt_id, context).as_message()

    def generate_avatar_response(
        self,
        query: str,
        chat_history: list[dict[str, str]],
    ):
        return self.avatar_service.generate_avatar_response(query, chat_history)

    def run_backup(self):
        return self.backup_service.create_backup()

    def run_recovery_drill(self, path: str):
        from pathlib import Path

        return self.backup_service.run_recovery_drill(Path(path))
