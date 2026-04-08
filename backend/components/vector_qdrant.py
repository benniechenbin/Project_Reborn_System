import difflib
import pickle
import jieba
from typing import List
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings # 确保引入了这个接口
from rank_bm25 import BM25Okapi

import utils as ut
from core.db_interface import BaseVectorDB
from config.settings import settings

# ==========================================
# 1. 核心转接头：本地向量模型适配器 (必须保留)
# ==========================================
class LocalEmbedder(Embeddings): 
    def __init__(self, encoder):
        self.encoder = encoder
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # 确保返回的是标准的 List[List[float]]
        embeddings = self.encoder.encode(texts)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
        
    def embed_query(self, text: str) -> List[float]:
        # 确保返回的是 List[float]
        embedding = self.encoder.encode(text)
        return embedding.tolist() if hasattr(embedding, "tolist") else embedding

# ==========================================
# 2. 向量库提供者：混合搜索与精排的核心逻辑
# ==========================================
class QdrantDBProvider(BaseVectorDB):
    def __init__(self):
        # 初始化模型时，把 encoder 喂给你的转接头
        self.encoder = ut.load_embedding_model()
        self.embedder = LocalEmbedder(self.encoder) 
        
        self.collection_name = "my_second_brain_kb"
        # ... 后续是你原本的 Qdrant 初始化代码 ...
        
        settings.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(settings.VECTOR_DB_PATH))

        if not self.client.collection_exists(self.collection_name):
            test_vector = self.embedder.embed_query("测试")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=len(test_vector), distance=Distance.COSINE),
            )

        self.vector_db = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embedder,
        )
        
        # === 引入 BM25 本地持久化支持 ===
        self.bm25_path = settings.VECTOR_DB_PATH / "bm25_corpus.pkl"
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
                print(f"📖 成功加载 BM25 索引，包含 {len(self.bm25_corpus)} 条切片。")

    def add_documents(self, documents: List[Document]):
        """存入文档时，同步更新 Qdrant 和 BM25"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = text_splitter.split_documents(documents)
        
        if splits:
            print(f"📦 准备存入 {len(splits)} 个切片...")
            # 1. 存入 Qdrant
            for i in range(0, len(splits), 4000):
                self.vector_db.add_documents(documents=splits[i : i + 4000])
            
            # 2. 存入 BM25 并持久化
            self.bm25_corpus.extend(splits)
            tokenized = [jieba.lcut(doc.page_content) for doc in self.bm25_corpus]
            self.bm25_model = BM25Okapi(tokenized)
            with open(self.bm25_path, "wb") as f:
                pickle.dump(self.bm25_corpus, f)
            print("✅ 混合检索双擎（Qdrant + BM25）写入完成！")

    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """【终极形态】BM25/Qdrant 双路召回 -> Rerank 精排 -> Difflib 去重"""
        recall_k = top_k * 4
        candidates_map = {} # 用 content 的 hash 作为 key 去重

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
        reranker = ut.load_reranker_model()
        pairs = [[query, doc.page_content] for doc in raw_docs]
        scores = reranker.predict(pairs)
        
        scored_docs = sorted(zip(raw_docs, scores), key=lambda x: x[1], reverse=True)

        # 4. 智能去重逻辑 (保留你原有的精髓)
        unique_docs = []
        seen_contents = []

        for doc, score in scored_docs:
            if score < -0.5: continue # 踢掉精排分数极低的伪关联
            
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
            # 1. 物理删除 Qdrant 集合
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
            
            # 2. 物理删除 BM25 本地缓存文件
            if self.bm25_path.exists():
                self.bm25_path.unlink() 
            
            # 3. 🛡️ 核心修复：立刻用同一个 client 重新建表
            test_vector = self.embedder.embed_query("测试")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=len(test_vector), distance=Distance.COSINE),
            )
            
            # 4. 清空内存中的 BM25 变量
            self.bm25_corpus = []
            self.bm25_model = None
            
            print("🗑️ 向量库与 BM25 索引已彻底清空并重置为初始状态！")
        except Exception as e:
            print(f"⚠️ 清空索引时出错: {e}")