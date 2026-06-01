import pytest
import numpy as np
from unittest.mock import MagicMock
from pathlib import Path
from langchain_core.documents import Document
from backend.memory.vector_store import QdrantDBProvider

@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_qdrant"

def test_vector_db_workflow(mocker, temp_db_path):
    # Mock settings to use temp path
    mocker.patch("backend.memory.vector_store.vector_qdrant.settings.vector_db_path", temp_db_path)
    
    # Mock models to return fixed size vectors/scores
    mock_encoder = MagicMock()
    # 假设向量维度是 384
    def mock_encode(texts):
        if isinstance(texts, str):
            return np.random.rand(384).astype(np.float32)
        return np.random.rand(len(texts), 384).astype(np.float32)
        
    mock_encoder.encode.side_effect = mock_encode
    mocker.patch("backend.memory.vector_store.vector_qdrant.load_embedding_model", return_value=mock_encoder)
    
    mock_reranker = MagicMock()
    mock_reranker.predict.side_effect = lambda x: np.array([0.9] * len(x))
    mocker.patch("backend.memory.vector_store.vector_qdrant.load_reranker_model", return_value=mock_reranker)

    db = QdrantDBProvider()
    
    # 1. 测试添加文档
    test_docs = [
        Document(page_content="关于诚实的价值观：我们永远不说谎。", metadata={"source": "values.md"}),
        Document(page_content="关于勤奋：我们要努力工作。", metadata={"source": "work.md"})
    ]
    db.add_documents(test_docs)
    
    # 2. 测试搜索
    results = db.search("为什么要诚实？", top_k=1)
    
    assert len(results) > 0
    assert "诚实" in results[0].page_content
    assert results[0].metadata["rerank_score"] == 0.9
