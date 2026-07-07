import wave
from collections.abc import Sequence
from pathlib import Path

from reborn_core.observability import logger


class AssetScanner:
    def __init__(
        self,
        obsidian_path: Path | str,
        audio_path: Path | str,
        target_folders: Sequence[str] | None = None,
    ) -> None:
        self.obsidian_path = Path(obsidian_path)
        self.audio_path = Path(audio_path)
        self.target_folders = tuple(target_folders or ())

    def count_notes_and_words(self) -> tuple[int, int]:
        """统计 Obsidian 中的笔记总数和估算总词数"""
        total_notes = 0
        total_words = 0

        if not self.obsidian_path.exists():
            logger.warning(f"Obsidian 路径不存在: {self.obsidian_path}")
            return 0, 0

        for root in self._note_roots():
            for md_file in root.rglob("*.md"):
                if self._is_obsidian_system_file(md_file):
                    continue

                total_notes += 1
                try:
                    content = md_file.read_text(encoding="utf-8")
                    # 简单统计：中文按字符数，英文按空格分词，这里取字符总数作为粗略估计
                    total_words += len(content.strip())
                except (OSError, UnicodeDecodeError) as e:
                    logger.error(f"读取文件失败 {md_file.name}: {e}")

        return total_notes, total_words

    def _note_roots(self) -> list[Path]:
        if not self.target_folders:
            return [self.obsidian_path]

        vault_root = self.obsidian_path.resolve()
        roots: list[Path] = []
        for folder in self.target_folders:
            folder_path = (self.obsidian_path / folder).resolve()
            if vault_root != folder_path and vault_root not in folder_path.parents:
                raise ValueError(f"目标文件夹不能位于 Obsidian 路径之外: {folder}")
            if not folder_path.exists():
                logger.warning(f"目标文件夹不存在，已跳过: {folder_path}")
                continue
            roots.append(folder_path)
        return roots

    def _is_obsidian_system_file(self, path: Path) -> bool:
        try:
            relative_parts = path.relative_to(self.obsidian_path).parts
        except ValueError:
            relative_parts = path.parts
        # 排除 Obsidian 的系统文件夹
        return ".obsidian" in relative_parts

    def count_audio_duration(self) -> float:
        """统计语音文件夹中所有 .wav 文件的总时长（分钟）"""
        total_seconds = 0.0

        if not self.audio_path.exists():
            logger.warning(f"音频路径不存在: {self.audio_path}")
            return 0.0

        for wav_file in self.audio_path.rglob("*.wav"):
            try:
                with wave.open(str(wav_file), "rb") as f:
                    params = f.getparams()
                    nframes = params[3]
                    framerate = params[2]
                    duration = nframes / float(framerate)
                    total_seconds += duration
            except (OSError, wave.Error) as e:
                logger.error(f"读取音频失败 {wav_file.name}: {e}")

        return round(total_seconds / 60, 1)  # 返回分钟数，保留一位小数
