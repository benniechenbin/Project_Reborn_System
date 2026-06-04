from unittest.mock import MagicMock

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("langchain_core")
pytest.importorskip("langchain_qdrant")
pytest.importorskip("qdrant_client")
pytest.importorskip("sentence_transformers")

from langchain_core.documents import Document  # noqa: E402

from reborn_core.domains.memory.vector_store import QdrantDBProvider  # noqa: E402


def test_vector_db_workflow(test_settings, tmp_path):
    mock_encoder = MagicMock()

    def mock_encode(texts):
        if isinstance(texts, str):
            return np.random.rand(384).astype(np.float32)
        return np.random.rand(len(texts), 384).astype(np.float32)

    mock_encoder.encode.side_effect = mock_encode
    mock_reranker = MagicMock()
    mock_reranker.predict.side_effect = lambda pairs: np.array([0.9] * len(pairs))

    db = QdrantDBProvider(
        app_settings=test_settings,
        vector_db_path=tmp_path / "test_qdrant",
        encoder=mock_encoder,
        reranker_loader=lambda: mock_reranker,
    )
    db.add_documents(
        [
            Document(
                page_content="关于诚实的价值观：我们永远不说谎。", metadata={"source": "values.md"}
            ),
            Document(page_content="关于勤奋：我们要努力工作。", metadata={"source": "work.md"}),
        ]
    )

    results = db.search("为什么要诚实？", top_k=1)

    assert len(results) > 0
    assert "诚实" in results[0].page_content
    assert results[0].metadata["rerank_score"] == 0.9
