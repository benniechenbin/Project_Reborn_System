import os
import wave
from pathlib import Path
from utils.logger import logger

class AssetScanner:
    def __init__(self, obsidian_path, audio_path):
        self.obsidian_path = Path(obsidian_path)
        self.audio_path = Path(audio_path)

    def count_notes_and_words(self):
        """统计 Obsidian 中的笔记总数和估算总词数"""
        total_notes = 0
        total_words = 0
        
        if not self.obsidian_path.exists():
            logger.warning(f"Obsidian 路径不存在: {self.obsidian_path}")
            return 0, 0

        # 遍历所有 .md 文件
        for md_file in self.obsidian_path.rglob("*.md"):
            # 排除 Obsidian 的系统文件夹
            if ".obsidian" in str(md_file):
                continue
            
            total_notes += 1
            try:
                content = md_file.read_text(encoding='utf-8')
                # 简单统计：中文按字符数，英文按空格分词，这里取字符总数作为粗略估计
                total_words += len(content.strip())
            except Exception as e:
                logger.error(f"读取文件失败 {md_file.name}: {e}")
        
        return total_notes, total_words

    def count_audio_duration(self):
        """统计语音文件夹中所有 .wav 文件的总时长（分钟）"""
        total_seconds = 0
        
        if not self.audio_path.exists():
            logger.warning(f"音频路径不存在: {self.audio_path}")
            return 0

        for wav_file in self.audio_path.rglob("*.wav"):
            try:
                with wave.open(str(wav_file), 'rb') as f:
                    params = f.getparams()
                    nframes = params[3]
                    framerate = params[2]
                    duration = nframes / float(framerate)
                    total_seconds += duration
            except Exception as e:
                logger.error(f"读取音频失败 {wav_file.name}: {e}")
        
        return round(total_seconds / 60, 1) # 返回分钟数，保留一位小数