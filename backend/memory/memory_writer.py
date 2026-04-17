# backend/memory/memory_writer.py
import os
from datetime import datetime
from pathlib import Path
from backend.core.logger import logger
from backend.core.settings import settings  # 引入 settings 获取 Obsidian 真实路径

class MemoryWriter:
    """
    数字分身物理记忆写入器 (路径 B：直接写入 Obsidian)
    负责将灵魂采访提炼的价值观转化为 Obsidian 笔记，实现数据的一体化。
    """
    def __init__(self):
        # 🚨 路径 B 核心变更：目标指向 Obsidian 仓库
        self.obsidian_root = Path(settings.active_obsidian_path)
        
        # 定义 AI 提炼记忆的专属存放目录
        self.reflections_dir = self.obsidian_root / "02_Values" / "00_AI_Reflections"
        
        # 虽然是 Path B，但孩子对话记录建议保留在项目本地，不建议混入个人知识库
        self.local_child_logs = Path(__file__).resolve().parent.parent.parent / "data" / "memories" / "child_dialogues"
        
        # 确保目录存在
        self._ensure_dirs()

    def _ensure_dirs(self):
        try:
            self.reflections_dir.mkdir(parents=True, exist_ok=True)
            self.local_child_logs.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 记忆写入通道已就绪: {self.reflections_dir}")
        except Exception as e:
            logger.error(f"❌ 无法创建记忆目录: {e}")

    def _generate_frontmatter(self, title: str, memory_type: str, tags: list) -> str:
        """生成符合 Obsidian 习惯的 YAML 前言"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags_str = "\n  - ".join([""] + (tags or []))
        
        return f"""---
title: "{title}"
date: {now}
type: {memory_type}
origin: "Soul_Interview"
tags:{tags_str}
---

"""

    def save_core_value(self, topic: str, content: str, tags: list = None) -> bool:
        """
        将提取的价值观落盘到 Obsidian：02_Values/00_AI_Reflections/
        """
        # 预处理文件名
        date_prefix = datetime.now().strftime("%Y%m%d_%H%M")
        safe_topic = topic.replace(" ", "_").replace("/", "_").replace("\\", "_")
        filename = f"{date_prefix}_{safe_topic}.md"
        filepath = self.reflections_dir / filename

        # 组装 Markdown 内容
        md_content = self._generate_frontmatter(topic, "core_value", tags or ["AI提炼", "价值观"])
        md_content += f"## 🧩 灵魂碎片提炼\n\n{content}\n\n"
        md_content += f"---\n> [!info] 提示\n> 此文档由 Project Reborn 灵魂采访室自动生成。你可以在 Obsidian 中随时进行人工修正，修正后的内容将在下次同步时生效。"

        try:
            filepath.write_text(md_content, encoding='utf-8')
            logger.info(f"🧠 记忆已注入 Obsidian: {filepath}")
            return True
        except Exception as e:
            logger.error(f"❌ 写入 Obsidian 失败: {e}")
            return False