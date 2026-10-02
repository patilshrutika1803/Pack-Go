from functools import lru_cache
from typing import Protocol

from rag.config import get_rag_settings


class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> object: ...


@lru_cache(maxsize=1)
def get_embedding_model(model_name: str | None = None) -> EmbeddingProvider:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name or get_rag_settings().embedding_model)


def embed_texts(texts: list[str], model: EmbeddingProvider | None = None) -> list[list[float]]:
    vectors = (model or get_embedding_model()).encode(texts)
    return vectors.tolist() if hasattr(vectors, "tolist") else [list(vector) for vector in vectors]