import os
import tempfile
from openai import OpenAI
from backend.config.settings import settings
from backend.observability.logger import logger

class STTEngine:
    def __init__(self):
        # 初始化 STT 客户端
        self.client = OpenAI(
            base_url=settings.stt_base_url,
            api_key=settings.stt_api_key
        )
        self.model = settings.stt_model_name

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        """将前端传来的音频字节流转换为文字"""
        if not audio_bytes:
            return ""
            
        try:
            logger.info("👂 接收到音频流，开始 Whisper 解析...")
            # Whisper API 需要一个真实的文件对象，所以我们用 tempfile 临时写到硬盘上
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            # 发送给 Whisper API
            with open(tmp_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language="zh"  # 强制指定中文，能大幅提升识别准确率和速度
                )
            
            # 阅后即焚，清理临时文件
            os.remove(tmp_path)
            
            logger.info(f"✅ 解析成功: {transcript.text}")
            return transcript.text
            
        except Exception as e:
            logger.error(f"❌ 语音转文字失败: {e}")
            return ""