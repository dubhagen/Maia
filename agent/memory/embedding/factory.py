"""Embedding provider factory.

An empty ``embedding_model`` leaves memory in keyword-only mode. A set model
id is embedded through the LiteLLM proxy. Vendor keys are never read.
"""

from typing import List

from common.log import logger

_embedding_logged = False


class LiteLLMEmbeddingProvider:
    """OpenAI-compatible /embeddings against the configured LiteLLM base."""

    def __init__(self, model: str, dimensions: int = 0):
        self.model = model
        self._dimensions = dimensions if dimensions and dimensions > 0 else 0

    def _embed_many(self, texts: List[str]) -> List[List[float]]:
        from models.litellm.endpoint import litellm_api_base, litellm_api_key
        from models.litellm.http_client import OpenAIHTTPClient

        cleaned = [text if isinstance(text, str) and text.strip() else " " for text in texts]
        client = OpenAIHTTPClient(api_key=litellm_api_key(), api_base=litellm_api_base(), timeout=90)
        payload = {"model": self.model, "input": cleaned}
        if self._dimensions:
            payload["dimensions"] = self._dimensions
        result = client.embeddings(**payload)
        items = result.get("data") or []
        if len(items) != len(cleaned):
            raise ValueError("embedding response count does not match input count")
        if any("index" in item for item in items):
            items = sorted(items, key=lambda item: item.get("index", 0))
        vectors = [item["embedding"] for item in items]
        if vectors and not self._dimensions:
            self._dimensions = len(vectors[0])
        return vectors

    def embed(self, text: str) -> List[float]:
        return self._embed_many([text])[0]

    def embed_query(self, text: str) -> List[float]:
        return self.embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        out: List[List[float]] = []
        step = 64
        for start in range(0, len(texts), step):
            out.extend(self._embed_many(texts[start:start + step]))
        return out

    @property
    def dimensions(self) -> int:
        if self._dimensions:
            return self._dimensions
        try:
            self.embed(" ")
        except Exception as exc:
            logger.warning("[EmbeddingFactory] could not probe embedding dimensions: %s", exc)
            return 0
        return self._dimensions


def create_default_embedding_provider():
    """Return a LiteLLM embedding client, or None when embeddings are off."""
    from config import conf
    from models.litellm.endpoint import LiteLLMConfigError, litellm_api_base

    model = conf().get("embedding_model")
    model = model.strip() if isinstance(model, str) else ""
    if not model:
        return None
    try:
        litellm_api_base()
    except LiteLLMConfigError as exc:
        logger.warning("[EmbeddingFactory] embeddings off: %s", exc)
        return None
    raw_dim = conf().get("embedding_dimensions") or 0
    try:
        dim = int(raw_dim)
    except (TypeError, ValueError):
        dim = 0
    provider = LiteLLMEmbeddingProvider(model, dim)
    _log_provider_once(f"litellm/{model}")
    return provider


def _log_provider_once(label: str) -> None:
    global _embedding_logged
    if _embedding_logged:
        return
    _embedding_logged = True
    logger.info("[EmbeddingFactory] using %s", label)
