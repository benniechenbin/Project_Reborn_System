from unittest.mock import MagicMock

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("langchain_core")
pytest.importorskip("langchain_qdrant")
pytest.importorskip("qdrant_client")
pytest.importorskip("sentence_transformers")

from langchain_core.documents import Document

from reborn_core.infrastructure.memory.vector_store import QdrantDBProvider


def test_vector_db_workflow(test_settings, tmp_path):
    mock_encoder = MagicMock()

    def mock_encode(texts):
        if isinstance(texts, str):
            return np.random.rand(384).astype(np.float32)
        return np.random.rand(len(texts), 384).astype(np.float32)

    mock_encoder.encode.side_effect = mock_encode
    mock_reranker = MagicMock()

    def mock_predict(pairs):
        scores = []
        for query, content in pairs:
            if "诚实" in content:
                scores.append(0.9)
            else:
                scores.append(0.1)
        return np.array(scores)

    mock_reranker.predict.side_effect = mock_predict

    db = QdrantDBProvider(
        app_settings=test_settings,
        vector_db_path=tmp_path / "test_qdrant",
        encoder=mock_encoder,
        reranker_loader=lambda: mock_reranker,
    )
    db.add_documents(
        [
            Document(
                page_content="关于诚实的价值观：我们永远不说谎。",
                metadata={"source": "values.md"},
            ),
            Document(
                page_content="关于勤奋：我们要努力工作。",
                metadata={"source": "work.md"},
            ),
        ]
    )

    results = db.search("为什么要诚实？", top_k=1)

    assert len(results) > 0
    assert "诚实" in results[0].page_content
    assert results[0].metadata["rerank_score"] == 0.9
    assert (tmp_path / "test_qdrant" / "bm25_index.json").exists()
    assert not (tmp_path / "test_qdrant" / "bm25_index.pkl").exists()


def test_legacy_pickle_bm25_index_is_ignored(test_settings, tmp_path):
    mock_encoder = MagicMock()

    def mock_encode(texts):
        if isinstance(texts, str):
            return np.random.rand(384).astype(np.float32)
        return np.random.rand(len(texts), 384).astype(np.float32)

    mock_encoder.encode.side_effect = mock_encode
    vector_path = tmp_path / "legacy_qdrant"
    vector_path.mkdir()
    (vector_path / "bm25_index.pkl").write_bytes(b"not a safe index")

    db = QdrantDBProvider(
        app_settings=test_settings,
        vector_db_path=vector_path,
        encoder=mock_encoder,
        reranker_loader=MagicMock(),
    )

    assert db.bm25_corpus == []
    assert db.bm25_model is None
