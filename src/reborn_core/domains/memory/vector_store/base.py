from abc import ABC, abstractmethod
from typing import Any


class BaseVectorDB(ABC):
    @abstractmethod
    def add_documents(self, documents: list[Any]) -> None:
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[Any]:
        pass

    def health_check(self) -> bool:
        return True
