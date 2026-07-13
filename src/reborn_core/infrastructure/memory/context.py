from datetime import datetime

from reborn_core.application.models import MemoryVaultLayout
from reborn_core.observability import logger


class ObsidianAvatarMemoryContext:
    """Loads ROM and recent reflection context from the Obsidian memory vault."""

    def __init__(self, layout: MemoryVaultLayout) -> None:
        self.layout = layout
        self.core_memories_path = layout.obsidian_root / layout.core_values_folder
        self.reflections_path = self.core_memories_path / layout.ai_reflections_folder

    def load_level_1_rom(self, now: datetime) -> str:
        persona_file = self.core_memories_path / "00_Master_Identity.md"
        directives_file = self.core_memories_path / "03_Prime_Directives.md"
        rom_content = ""
        if persona_file.exists():
            rom_content += persona_file.read_text(encoding="utf-8") + "\n"
        if directives_file.exists():
            rom_content += "### 最高行为准则\n" + directives_file.read_text(encoding="utf-8")
        env_info = (
            f"\n---\n当前现实时间：{now.strftime('%Y-%m-%d %H:%M')}，星期{now.weekday() + 1}。"
        )
        return rom_content + env_info

    def load_level_2_personality(self) -> str:
        if not self.reflections_path.exists():
            return "（近期性格稳定，暂无动态更新）"
        files = sorted(
            self.reflections_path.glob("*.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:3]
        summaries = []
        for path in files:
            try:
                content = path.read_text(encoding="utf-8")
                summaries.append(f"【近期感悟】：{content}")
            except OSError as exc:
                logger.error("读取反思文件失败: {}", exc)
        return "\n\n".join(summaries) if summaries else "（暂无近期性格碎片）"
