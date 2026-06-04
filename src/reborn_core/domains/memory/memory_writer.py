import json
import re
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from reborn_core.config import Settings, get_settings
from reborn_core.observability import logger


class MemoryWriter:
    def __init__(
        self,
        app_settings: Settings | None = None,
        obsidian_root: Path | None = None,
    ) -> None:
        settings = app_settings or get_settings()
        self.obsidian_root = (
            obsidian_root
            or settings.active_obsidian_path
            or (settings.base_dir / "data" / "memories")
        )
        self.obsidian_root.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """
        核心升级：文件名净化器
        防范大模型在生成的标题中带有冒号、斜杠等非法路径字符，导致落盘崩溃。
        """
        clean_name = re.sub(r'[\\/*?:"<>|]', " - ", filename)
        return clean_name.strip()

    def _ensure_yaml_frontmatter(
        self,
        content: str,
        default_category: str,
        source_ref: str | None = None,
    ) -> str:
        """
        核心升级：YAML 兜底引擎
        虽然我们会通过 Prompt 强制 LLM 输出高级 YAML 标签，但如果 LLM 发生截断或幻觉，
        此方法会强行补全基础 Metadata，确保 Obsidian 解析不报错。
        """
        content = content.strip()
        source_line = (
            f"source_artifact: {json.dumps(source_ref, ensure_ascii=False)}\n" if source_ref else ""
        )
        if not content.startswith("---"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            fallback_yaml = (
                f"---\ndate: {now}\ncategory: {default_category}\n"
                f"{source_line}tags: [AI_Fallback]\n---\n\n"
            )
            return fallback_yaml + content
        if source_line and "source_artifact:" not in content:
            return content.replace("---\n", f"---\n{source_line}", 1)
        return content

    def save_source_transcript(self, title: str, content: str, mode: str) -> str:
        """在派生记忆目录之外持久化不可变的原始资料。"""
        target_dir = self.obsidian_root / "01_Source_Artifacts" / "Interviews"
        now = datetime.now(UTC)
        safe_title = self._sanitize_filename(title) or "untitled"
        target_path = target_dir / f"{now.strftime('%Y%m%dT%H%M%S.%fZ')}_{safe_title}.md"
        source_content = (
            "---\n"
            f"captured_at: {now.isoformat()}\n"
            f"interview_mode: {mode}\n"
            "artifact_type: interview_transcript\n"
            "---\n\n"
            f"{content.strip()}\n"
        )
        self._write_atomic(target_path, source_content)
        logger.info(f"✅ 原始访谈已归档: {target_path}")
        return target_path.relative_to(self.obsidian_root).as_posix()

    def save_core_value(
        self,
        title: str,
        content: str,
        source_ref: str | None = None,
    ) -> bool:
        """保存价值观/认知类记忆 (ROM) 到 00_AI_Reflections"""
        target_dir = self.obsidian_root / "02_Values" / "00_AI_Reflections"
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = self._sanitize_filename(title)
        if not safe_title.endswith(".md"):
            safe_title += ".md"

        file_path = target_dir / safe_title

        try:
            # 注入/校验 YAML 头
            final_content = self._ensure_yaml_frontmatter(content, "02_Values", source_ref)
            self._write_atomic(file_path, final_content)
            logger.info(f"✅ 成功保存价值观记忆: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存价值观记忆失败: {e}")
            return False

    def save_story(
        self,
        title: str,
        content: str,
        source_ref: str | None = None,
    ) -> bool:
        """保存往事/经历类记忆 (RAM) 到 03_Stories"""
        target_dir = self.obsidian_root / "03_Stories"
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = self._sanitize_filename(title)
        if not safe_title.endswith(".md"):
            safe_title += ".md"

        file_path = target_dir / safe_title

        try:
            # 注入/校验 YAML 头
            final_content = self._ensure_yaml_frontmatter(content, "03_Stories", source_ref)
            self._write_atomic(file_path, final_content)
            logger.info(f"✅ 成功保存故事记忆: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存故事记忆失败: {e}")
            return False

    def read_master_identity(self) -> str:
        """读取当前的身份核文件"""
        path = self.obsidian_root / "02_Values" / "00_Master_Identity.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "（目前身份档案为空。造物主尚未提供核心身份信息。）"

    def save_master_identity(self, content: str) -> bool:
        """覆盖式写入身份核文件"""
        target_dir = self.obsidian_root / "02_Values"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / "00_Master_Identity.md"
        try:
            if target_path.exists():
                old_content = target_path.read_text(encoding="utf-8")
                if old_content == content:
                    return True
                history_dir = target_dir / "00_Identity_History"
                history_path = history_dir / (
                    datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ") + ".md"
                )
                self._write_atomic(history_path, old_content)

            self._write_atomic(target_path, content)

            logger.info("✅ 身份核 (Master Identity) 已通过原子操作安全更新！")
            return True

        except Exception as e:
            logger.error(f"❌ 更新身份核失败: {e}")
            return False

    def _write_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
