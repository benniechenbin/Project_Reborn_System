# backend/memory/vector_store/model_loader.py
import os
import functools
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from backend.core.logger import logger

# 获取项目根目录，确保绝对路径的稳固
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LOCAL_MODELS_DIR = PROJECT_ROOT / "data" / "local_models"

@functools.lru_cache(maxsize=1)
def load_embedding_model():
    """加载 Embedding 模型：优先本地，缺失时自动下载并固化"""
    model_name = "BAAI/bge-small-zh-v1.5"
    # 定义项目内的专属存放路径
    local_model_path = LOCAL_MODELS_DIR / "bge-small-zh-v1.5"

    try:
        if local_model_path.exists():
            logger.info(f"📦 发现本地 Embedding 模型，执行断网加载...")
            return SentenceTransformer(str(local_model_path))
        else:
            logger.info(f"🌐 正在从镜像源首次下载 Embedding 模型: {model_name} ...")
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            model = SentenceTransformer(model_name)
            
            # 下载完毕后，立刻保存到项目的 local_models 目录中
            local_model_path.mkdir(parents=True, exist_ok=True)
            model.save(str(local_model_path))
            logger.info(f"✅ Embedding 模型已永久固化至: {local_model_path}")
            return model
            
    except Exception as e:
        logger.error(f"❌ Embedding 模型加载或保存失败: {e}")
        raise

@functools.lru_cache(maxsize=1)
def load_reranker_model():
    """加载重排序模型 (支持本地固化)"""
    local_model_path = LOCAL_MODELS_DIR / "bge-reranker-base"

    try:
        if local_model_path.exists():
            logger.info(f"📦 发现本地 Reranker 模型，执行断网加载...")
            return CrossEncoder(str(local_model_path), max_length=512)
        else:
            logger.info("🌐 正在从镜像源执行首次下载 Reranker...")
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            model = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
            
            local_model_path.mkdir(parents=True, exist_ok=True)
            model.save(str(local_model_path))
            logger.info(f"✅ Reranker 模型已永久固化至: {local_model_path}")
            return model
            
    except Exception as e:
        logger.error(f"❌ Reranker 模型加载或保存失败: {e}")
        raise