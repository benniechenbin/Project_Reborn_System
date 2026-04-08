# backend/core/db_interface.py
from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document

class BaseVectorDB(ABC):
    """
    🗄️ 向量数据库抽象接口 (契约类)
    任何具体的向量库引擎 (如 Qdrant, Milvus) 都必须继承此基类并实现以下方法。
    这保证了上层 RAG 业务逻辑与底层数据库存储的彻底解耦。
    """

    @abstractmethod
    def add_documents(self, documents: List[Document]):
        """
        接收 LangChain Document 列表，并将其切片、向量化后存入数据库
        """
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """
        接收用户的查询字符串，返回最相关的 Top K 个 Document 对象
        """
        pass

    @abstractmethod
    def clear(self):
        """
        彻底清空集合中的所有向量与缓存数据，重置库状态
        """
        pass