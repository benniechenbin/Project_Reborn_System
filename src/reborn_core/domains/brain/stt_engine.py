import os
import tempfile
from funasr import AutoModel
from reborn_core.core.config import settings
from reborn_core.core.logger import logger

settings.models_dir.mkdir(parents=True, exist_ok=True)
os.environ["MODELSCOPE_CACHE"] = str(settings.models_dir)

class STTEngine:
    def __init__(self):
        logger.info(f"⏳ 准备加载达摩 ASR...")
        logger.info(f"📁 模型路径已锁定至: {settings.models_dir}")
        
        # 首次运行会自动下载到我们刚刚指定的 data/local_models/ 里
        self.model = AutoModel(
            model="paraformer-zh", 
            vad_model="fsmn-vad", 
            punc_model="ct-punc", 
            disable_update=True
        )
        logger.info("✅ 达摩 ASR 准备完毕！本地隐私听觉已完全激活。")

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        """将前端传来的音频字节流转换为文字"""
        if not audio_bytes:
            return ""
            
        try:
            logger.info("👂 接收到音频流，开始本地离线解析...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            # 执行离线识别
            res = self.model.generate(input=tmp_path, batch_size_s=300)
            os.remove(tmp_path)
            
            if res and len(res) > 0:
                transcript_text = res[0].get('text', '')
                logger.info(f"✅ 解析成功: {transcript_text}")
                return transcript_text
            
            return ""
        except Exception as e:
            logger.error(f"❌ 本地语音解析失败: {e}")
            return ""