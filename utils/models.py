import os
import functools
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from backend.observability.logger import logger

def load_embedding_model(model_name: str = "BAAI/bge-small-zh-v1.5"):
    """加载 Embedding 模型：优先本地，缺失时自动下载"""
    try:
        # 尝试从默认缓存目录加载
        model = SentenceTransformer(model_name)
        logger.info(f"✅ Embedding 模型加载完成: {model_name}")
        return model
    except Exception as e:
        logger.error(f"❌ 模型加载失败: {e}")
        raise

@functools.lru_cache(maxsize=1)
def load_reranker_model():
    """加载重排序模型 (支持本地固化)"""
    # 这里的路径改为 Project Reborn 内部的存储路径
    local_model_path = Path("backend/models/bge-reranker-base")

    if local_model_path.exists():
        logger.info(f"📦 发现本地 Reranker 模型，执行断网加载")
        return CrossEncoder(str(local_model_path), max_length=512)
    else:
        logger.info("🌐 正在从镜像源执行首次下载 Reranker...")
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        model = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
        
        # 自动固化，下次就不用下载了
        local_model_path.mkdir(parents=True, exist_ok=True)
        model.save(str(local_model_path))
        return model