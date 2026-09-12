from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from rag.embeddings import EmbeddingProvider, embed_texts
from rag.vector_store import get_knowledge_collection


DEFAULT_TOP_K = 5
MAX_TOP_K = 50
FILTER_FIELDS = ("destination", "category", "document_type")


class RetrievedDocument(BaseModel):
    content: str
    document_id: str
    source: str
    filename: str
    page: int
    chunk_index: int
    destination: str
    category: str
    document_type: str
    distance: float | None = None


def _validate_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain non-whitespace text")
    return query.strip()


def _validate_top_k(top_k: int) -> int:
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise ValueError("top_k must be an integer")
    if top_k < 1 or top_k > MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
    return top_k


def _build_where(
    destination: str | None,
    category: str | None,
    document_type: str | None,
) -> dict[str, Any] | None:
    conditions = [
        {field: value}
        for field, value in zip(
            FILTER_FIELDS,
            (destination, category, document_type),
            strict=True,
        )
        if value is not None
    ]
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def retrieve_documents(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    destination: str | None = None,
    category: str | None = None,
    document_type: str | None = None,
    *,
    collection=None,
    embedding_model: EmbeddingProvider | None = None,
    persist_directory: str | None = None,
) -> list[RetrievedDocument]:
    """Retrieve ranked travel-knowledge chunks without generating an answer.

    Chroma's returned ``distance`` is preserved as-is; lower values indicate
    closer matches for the collection's configured distance function.
    """
    normalized_query = _validate_query(query)
    validated_top_k = _validate_top_k(top_k)
    where = _build_where(destination, category, document_type)
    knowledge_collection = collection or get_knowledge_collection(
        persist_directory=persist_directory
    )
    if knowledge_collection.count() == 0:
        return []

    query_embedding = embed_texts([normalized_query], embedding_model)[0]
    result = knowledge_collection.query(
        query_embeddings=[query_embedding],
        n_results=min(validated_top_k, knowledge_collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0] or []
    metadatas = result.get("metadatas", [[]])[0] or []
    ids = result.get("ids", [[]])[0] or []
    distances = result.get("distances", [[]])[0] or []

    return [
        RetrievedDocument(
            content=content,
            document_id=metadata["document_id"],
            source=metadata["source"],
            filename=metadata["filename"],
            page=metadata["page"],
            chunk_index=metadata["chunk_index"],
            destination=metadata["destination"],
            category=metadata["category"],
            document_type=metadata["document_type"],
            distance=distances[index] if index < len(distances) else None,
        )
        for index, (content, metadata) in enumerate(zip(documents, metadatas, strict=True))
    ]
