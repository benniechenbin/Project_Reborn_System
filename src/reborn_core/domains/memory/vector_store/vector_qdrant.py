import difflib
import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jieba
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from rank_bm25 import BM25Okapi

# ✅ 修复 1：正确的函数级导入
from reborn_core.config import Settings
from reborn_core.domains.memory.vector_store.base import BaseVectorDB
from reborn_core.domains.memory.vector_store.model_loader import (
    load_embedding_model,
    load_reranker_model,
)
from reborn_core.observability import logger


# ==========================================
# 1. 核心转接头：本地向量模型适配器
# ==========================================
class LocalEmbedder(Embeddings):
    def __init__(self, encoder):
        self.encoder = encoder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.encoder.encode(texts)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings

    def embed_query(self, text: str) -> list[float]:
        embedding = self.encoder.encode(text)
        return embedding.tolist() if hasattr(embedding, "tolist") else embedding


# ==========================================
# 2. 向量库提供者：混合搜索与精排的核心逻辑
# ==========================================
class QdrantDBProvider(BaseVectorDB):
    def __init__(
        self,
        app_settings: Settings,
        vector_db_path: Path | None = None,
        encoder: Any | None = None,
        reranker_loader: Callable[[Path, str], Any] = load_reranker_model,
    ) -> None:
        self.encoder = encoder or load_embedding_model(
            models_dir=app_settings.resolved_models_dir,
            hf_mirror=app_settings.hf_mirror,
        )
        self.embedder = LocalEmbedder(self.encoder)

        import inspect

        try:
            sig = inspect.signature(reranker_loader)
            params = [
                p
                for p in sig.parameters.values()
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                )
            ]
            has_params = len(params) > 0
        except (ValueError, TypeError):
            has_params = True

        self._reranker_loader: Callable[[], Any]
        if has_params:
            self._reranker_loader = lambda: reranker_loader(
                app_settings.resolved_models_dir,
                app_settings.hf_mirror,
            )
        else:
            self._reranker_loader = reranker_loader  # type: ignore[assignment]

        self.vector_db_path = vector_db_path or app_settings.resolved_vector_db_path
        self.vector_db_path.mkdir(parents=True, exist_ok=True)
        self.bm25_path = self.vector_db_path / "bm25_index.json"
        self.legacy_bm25_pickle_path = self.vector_db_path / "bm25_index.pkl"
        self.client = QdrantClient(path=str(self.vector_db_path))
        self.collection_name = "reborn_memory"

        if not self.client.collection_exists(self.collection_name):
            logger.info(
                "正在为新检索代次初始化 Qdrant 集合：{}，存储路径：{}",
                self.collection_name,
                self.vector_db_path,
            )
            vector_size = len(self.encoder.encode("测试内容"))

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("新检索代次的 Qdrant 集合初始化完成")

        self.vector_db = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embedder,
        )

        self.bm25_corpus: list[Document] = []
        self.bm25_model: BM25Okapi | None = None
        self._load_bm25()

    def _load_bm25(self) -> None:
        """加载本地 BM25 索引"""
        if not self.bm25_path.exists():
            if self.legacy_bm25_pickle_path.exists():
                logger.warning(
                    "忽略旧版 pickle BM25 索引：{}。请重新同步以生成安全 JSON 索引。",
                    self.legacy_bm25_pickle_path,
                )
            return
        try:
            payload = json.loads(self.bm25_path.read_text(encoding="utf-8"))
            items = payload.get("documents", []) if isinstance(payload, dict) else []
            self.bm25_corpus = [
                Document(
                    page_content=str(item["page_content"]),
                    metadata=dict(item.get("metadata") or {}),
                )
                for item in items
                if isinstance(item, dict) and "page_content" in item
            ]
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("BM25 JSON 索引读取失败，将在下次同步时重建: {}", exc)
            self.bm25_corpus = []
            self.bm25_model = None
            return
        self._rebuild_bm25()
        if self.bm25_corpus:
            logger.info(
                "📖 成功加载 BM25 索引，包含 {} 条切片。",
                len(self.bm25_corpus),
            )

    def add_documents(self, documents: list[Document]) -> None:
        """针对手写感性文档优化的‘深度切片’方案"""
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=150,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        )

        all_splits = []
        for doc in documents:
            source_title = Path(doc.metadata.get("source", "")).stem
            md_header_splits = md_splitter.split_text(doc.page_content)

            for header_split in md_header_splits:
                header_split.page_content = (
                    f"【来自笔记：{source_title}】\n{header_split.page_content}"
                )
                header_split.metadata.update(doc.metadata)
                final_splits = text_splitter.split_documents([header_split])
                all_splits.extend(final_splits)

        if all_splits:
            logger.info(
                "🧬 深度审计完成：已将感性手稿转化为 {} 个高保真记忆切片...",
                len(all_splits),
            )
            self.vector_db.add_documents(documents=all_splits)

            self.bm25_corpus.extend(all_splits)
            self._rebuild_bm25()
            self._save_bm25()
            logger.info("✅ 混合检索双擎已完成高保真写入！")

    def search(self, query: str, top_k: int = 5) -> list[Document]:
        """【终极形态】BM25/Qdrant 双路召回 -> Rerank 精排 -> Difflib 去重"""
        recall_k = top_k * 4
        candidates_map: dict[str, Document] = {}

        # 1. Qdrant 向量召回（负责理解语义）
        vec_results = self.vector_db.similarity_search(query, k=recall_k)
        for doc in vec_results:
            candidates_map[doc.page_content] = doc

        # 2. BM25 稀疏召回（负责理解关键词）
        if self.bm25_model:
            tokenized_query = jieba.lcut(query)
            bm25_results = self.bm25_model.get_top_n(tokenized_query, self.bm25_corpus, n=recall_k)
            for doc in bm25_results:
                candidates_map[doc.page_content] = doc

        raw_docs = list(candidates_map.values())
        if not raw_docs:
            return []

        # 3. Cross-Encoder 精排（负责严格打分）
        # 直接调用函数，并利用 LRU 缓存高效加载
        reranker = self._reranker_loader()
        pairs = [[query, doc.page_content] for doc in raw_docs]
        scores = reranker.predict(pairs)

        scored_docs = sorted(zip(raw_docs, scores), key=lambda x: x[1], reverse=True)

        # 4. 智能去重逻辑
        unique_docs: list[Document] = []
        seen_contents: list[str] = []

        for doc, score in scored_docs:
            if score < -0.5:
                continue

            new_text = doc.page_content.strip()
            is_duplicate = False
            for seen in seen_contents:
                if difflib.SequenceMatcher(None, new_text, seen).ratio() > 0.85:
                    is_duplicate = True
                    break

            if not is_duplicate:
                doc.metadata["rerank_score"] = float(score)
                unique_docs.append(doc)
                seen_contents.append(new_text)

            if len(unique_docs) >= top_k:
                break

        return unique_docs

    def health_check(self) -> bool:
        # bm25_path 是可选的加速索引，不是必要条件；
        # 只要 Qdrant collection 存在，检索代次即为健康状态。
        return self.client.collection_exists(self.collection_name)

    def _rebuild_bm25(self) -> None:
        if not self.bm25_corpus:
            self.bm25_model = None
            return
        tokenized = [jieba.lcut(doc.page_content) for doc in self.bm25_corpus]
        self.bm25_model = BM25Okapi(tokenized)

    def _save_bm25(self) -> None:
        payload = {
            "schema_version": 1,
            "documents": [
                {
                    "page_content": doc.page_content,
                    "metadata": _metadata_to_json(doc.metadata),
                }
                for doc in self.bm25_corpus
            ],
        }
        temp_path = self.bm25_path.with_name(f".{self.bm25_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(temp_path, self.bm25_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()


def _metadata_to_json(metadata: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _jsonable_metadata_value(value) for key, value in metadata.items()}


def _jsonable_metadata_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_jsonable_metadata_value(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable_metadata_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable_metadata_value(item) for key, item in value.items()}
    return str(value)
