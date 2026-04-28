import difflib
import pickle
import jieba
from typing import List
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from rank_bm25 import BM25Okapi
from pathlib import Path

# ✅ 修复 1：正确的函数级导入
from backend.memory.vector_store.model_loader import load_embedding_model, load_reranker_model 
from backend.observability.logger import logger
from backend.memory.vector_store.base import BaseVectorDB
from backend.config.settings import settings

# ==========================================
# 1. 核心转接头：本地向量模型适配器 
# ==========================================
class LocalEmbedder(Embeddings): 
    def __init__(self, encoder):
        self.encoder = encoder
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.encoder.encode(texts)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
        
    def embed_query(self, text: str) -> List[float]:
        embedding = self.encoder.encode(text)
        return embedding.tolist() if hasattr(embedding, "tolist") else embedding

# ==========================================
# 2. 向量库提供者：混合搜索与精排的核心逻辑
# ==========================================
class QdrantDBProvider(BaseVectorDB):
    def __init__(self):
        self.encoder = load_embedding_model()
        self.embedder = LocalEmbedder(self.encoder)                
        self.vector_db_path = Path(settings.vector_db_path)       
        self.bm25_path = self.vector_db_path / "bm25_index.pkl"         
        self.client = QdrantClient(path=str(self.vector_db_path))
        self.collection_name = "reborn_memory"
        
        if not self.client.collection_exists(self.collection_name):
            logger.info(f"🆕 发现是首次运行，正在创建 Qdrant 集合: {self.collection_name}")
            vector_size = len(self.encoder.encode("测试内容"))
            
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("✅ 集合创建成功！")

        self.vector_db = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embedder,
        )   
         
        self.bm25_corpus = []
        self.bm25_model = None
        self._load_bm25()

    def _load_bm25(self):
        """加载本地 BM25 索引"""
        if self.bm25_path.exists():
            with open(self.bm25_path, "rb") as f:
                self.bm25_corpus = pickle.load(f)
            if self.bm25_corpus:
                tokenized = [jieba.lcut(doc.page_content) for doc in self.bm25_corpus]
                self.bm25_model = BM25Okapi(tokenized)
                logger.info(f"📖 成功加载 BM25 索引，包含 {len(self.bm25_corpus)} 条切片。")

    def add_documents(self, documents: List[Document]):
        """针对手写感性文档优化的‘深度切片’方案"""
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, 
            chunk_overlap=120,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""]
        )

        all_splits = []
        for doc in documents:
            source_title = Path(doc.metadata.get("source", "")).stem
            md_header_splits = md_splitter.split_text(doc.page_content)
            
            for header_split in md_header_splits:
                header_split.page_content = f"【来自笔记：{source_title}】\n{header_split.page_content}"
                header_split.metadata.update(doc.metadata)
                final_splits = text_splitter.split_documents([header_split])
                all_splits.extend(final_splits)

        if all_splits:
            logger.info(f"🧬 深度审计完成：已将感性手稿转化为 {len(all_splits)} 个高保真记忆切片...")
            self.vector_db.add_documents(documents=all_splits)
            
            self.bm25_corpus.extend(all_splits)
            tokenized = [jieba.lcut(doc.page_content) for doc in self.bm25_corpus]
            self.bm25_model = BM25Okapi(tokenized)
            with open(self.bm25_path, "wb") as f:
                pickle.dump(self.bm25_corpus, f)
            logger.info("✅ 混合检索双擎已完成高保真写入！")

    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """【终极形态】BM25/Qdrant 双路召回 -> Rerank 精排 -> Difflib 去重"""
        recall_k = top_k * 4
        candidates_map = {} 

        # 1. Qdrant 向量召回 (懂语义)
        vec_results = self.vector_db.similarity_search(query, k=recall_k)
        for doc in vec_results:
            candidates_map[doc.page_content] = doc

        # 2. BM25 稀疏召回 (懂关键词)
        if self.bm25_model:
            tokenized_query = jieba.lcut(query)
            bm25_results = self.bm25_model.get_top_n(tokenized_query, self.bm25_corpus, n=recall_k)
            for doc in bm25_results:
                candidates_map[doc.page_content] = doc

        raw_docs = list(candidates_map.values())
        if not raw_docs:
            return []

        # 3. Cross-Encoder 精排 (严格打分)
        # ✅ 修复 1：直接调用函数，利用 LRU Cache 高效加载
        reranker = load_reranker_model()
        pairs = [[query, doc.page_content] for doc in raw_docs]
        scores = reranker.predict(pairs)
        
        scored_docs = sorted(zip(raw_docs, scores), key=lambda x: x[1], reverse=True)

        # 4. 智能去重逻辑
        unique_docs = []
        seen_contents = []

        for doc, score in scored_docs:
            if score < -0.5: continue 
            
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

    def clear(self):
        try:
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
            
            if self.bm25_path.exists():
                self.bm25_path.unlink() 
            
            test_vector = self.embedder.embed_query("测试")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=len(test_vector), distance=Distance.COSINE),
            )
            
            self.bm25_corpus = []
            self.bm25_model = None
            
            logger.info("🗑️ 向量库与 BM25 索引已彻底清空并重置为初始状态！")
        except Exception as e:
            logger.exception(f"⚠️ 清空索引时出错: {e}")