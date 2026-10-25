"""Embedding types for memory.

Vectors are produced by the LiteLLM client in ``factory.py`` when
``embedding_model`` is set. This module keeps the provider interface and
the in-memory cache. It does not call a vendor host.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional


class EmbeddingProvider(ABC):
    """Base class for embedding providers"""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text (treated as a query by default)"""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (treated as documents)"""
        pass

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query string (may apply vendor instruction prefix)"""
        return self.embed(text)

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Effective embedding dimensions"""
        pass



class EmbeddingCache:
    """In-memory cache for embeddings to avoid recomputation"""

    def __init__(self):
        self.cache = {}

    def get(self, text: str, provider: str, model: str) -> Optional[List[float]]:
        key = self._compute_key(text, provider, model)
        return self.cache.get(key)

    def put(self, text: str, provider: str, model: str, embedding: List[float]):
        key = self._compute_key(text, provider, model)
        self.cache[key] = embedding

    @staticmethod
    def _compute_key(text: str, provider: str, model: str) -> str:
        content = f"{provider}:{model}:{text}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def clear(self):
        self.cache.clear()


def create_embedding_provider(
    provider: str = "litellm",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    extra_headers: Optional[dict] = None,
    dimensions: Optional[int] = None,
    source_tagged: Optional[bool] = None,
) -> EmbeddingProvider:
    """Vendor embedding providers are removed.

    Use ``create_default_embedding_provider`` with ``embedding_model`` set.
    This function refuses every call so a leftover vendor name cannot open
    a connection to that vendor's host.
    """
    del provider, model, api_key, api_base, extra_headers, dimensions, source_tagged
    raise RuntimeError(
        "Vendor embedding providers are removed. "
        "Set embedding_model and use the LiteLLM proxy."
    )
