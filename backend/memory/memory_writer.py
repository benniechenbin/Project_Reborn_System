import re
import os
from datetime import datetime
from pathlib import Path
from backend.observability.logger import logger
from backend.config.settings import settings

class MemoryWriter:
    def __init__(self):
        # 💡 使用纯净版 settings 提供的动态路径，再配合相对路径做 Fallback
        try:
            target_path = settings.active_obsidian_path
            if not target_path:
                target_path = "data/memories" # 如果未配置，降级为项目内目录
        except Exception as e:
            logger.warning(f"无法获取系统 Obsidian 路径，使用默认路径: {e}")
            target_path = "data/memories"
            
        self.obsidian_root = Path(target_path)
        self.obsidian_root.mkdir(parents=True, exist_ok=True)
        
    def _sanitize_filename(self, filename: str) -> str:
        """
        核心升级：文件名净化器
        防范大模型在生成的标题中带有冒号、斜杠等非法路径字符，导致落盘崩溃。
        """
        clean_name = re.sub(r'[\\/*?:"<>|]', " - ", filename)
        return clean_name.strip()

    def _ensure_yaml_frontmatter(self, content: str, default_category: str) -> str:
        """
        核心升级：YAML 兜底引擎
        虽然我们会通过 Prompt 强制 LLM 输出高级 YAML 标签，但如果 LLM 发生截断或幻觉，
        此方法会强行补全基础 Metadata，确保 Obsidian 解析不报错。
        """
        content = content.strip()
        if not content.startswith("---"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            fallback_yaml = (
                f"---\n"
                f"date: {now}\n"
                f"category: {default_category}\n"
                f"tags: [AI_Fallback]\n"
                f"---\n\n"
            )
            return fallback_yaml + content
        return content

    def save_core_value(self, title: str, content: str) -> bool:
        """保存价值观/认知类记忆 (ROM) 到 00_AI_Reflections"""
        target_dir = self.obsidian_root / "02_Values" / "00_AI_Reflections"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = self._sanitize_filename(title)
        if not safe_title.endswith(".md"):
            safe_title += ".md"
            
        file_path = target_dir / safe_title
        
        try:
            # 注入/校验 YAML 头
            final_content = self._ensure_yaml_frontmatter(content, "02_Values")
            file_path.write_text(final_content, encoding='utf-8')
            logger.info(f"✅ 成功保存价值观记忆: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存价值观记忆失败: {e}")
            return False

    def save_story(self, title: str, content: str) -> bool:
        """保存往事/经历类记忆 (RAM) 到 03_Stories"""
        target_dir = self.obsidian_root / "03_Stories"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = self._sanitize_filename(title)
        if not safe_title.endswith(".md"):
            safe_title += ".md"
            
        file_path = target_dir / safe_title
        
        try:
            # 注入/校验 YAML 头
            final_content = self._ensure_yaml_frontmatter(content, "03_Stories")
            file_path.write_text(final_content, encoding='utf-8')
            logger.info(f"✅ 成功保存故事记忆: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存故事记忆失败: {e}")
            return False

    def read_master_identity(self) -> str:
        """读取当前的身份核文件"""
        path = self.obsidian_root / "02_Values" / "00_Master_Identity.md"
        if path.exists():
            return path.read_text(encoding='utf-8')
        return "（目前身份档案为空。造物主尚未提供核心身份信息。）"

    def save_master_identity(self, content: str) -> bool:
        """覆盖式写入身份核文件"""
        target_dir = self.obsidian_root / "02_Values"
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "00_Master_Identity.md"
        try:
            # 身份核可以直接写入，因为它是一个特殊的聚合文件
            path.write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f"❌ 更新身份核失败: {e}")
            return False