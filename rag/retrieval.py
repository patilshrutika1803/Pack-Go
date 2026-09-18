from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from rag.config import get_rag_settings
from rag.embeddings import EmbeddingProvider, embed_texts
from rag.vector_store import get_knowledge_collection
from logger.logging import get_logger


DEFAULT_TOP_K = 5
MAX_TOP_K = 50
FILTER_FIELDS = ("destination", "category", "document_type")
logger = get_logger(__name__)


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


class RetrievalQualityResult(BaseModel):
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    query: str
    retrieval_success: bool
    relevance_status: str
    number_of_results: int
    best_distance: float | None = None
    average_distance: float | None = None
    whether_retry_was_used: bool = False
    rewritten_query: str | None = None


_REWRITE_TERMS = "travel guide destination transportation seasons safety accommodation activities"


def _rewrite_query(query: str) -> str:
    """Add retrieval-oriented terms without introducing factual claims."""
    normalized_query = " ".join(query.split())
    query_terms = set(re.findall(r"[a-z0-9]+", normalized_query.lower()))
    if query_terms.intersection({"goa", "beach", "beaches", "transport", "reach", "visit"}):
        return f"{normalized_query} travel guide"
    return f"{normalized_query} {_REWRITE_TERMS}"


def _deduplicate_documents(documents: list[RetrievedDocument]) -> list[RetrievedDocument]:
    unique_documents = []
    seen = set()
    for document in documents:
        key = (document.document_id, document.page, document.chunk_index, document.content)
        if key not in seen:
            seen.add(key)
            unique_documents.append(document)
    return unique_documents


def _quality_for(
    query: str,
    documents: list[RetrievedDocument],
    distance_threshold: float,
    *,
    retry_was_used: bool = False,
    rewritten_query: str | None = None,
) -> RetrievalQualityResult:
    distances = [document.distance for document in documents if document.distance is not None]
    best_distance = min(distances) if distances else None
    average_distance = sum(distances) / len(distances) if distances else None
    if not documents:
        relevance_status = "no_results"
    elif best_distance is not None and best_distance > distance_threshold:
        relevance_status = "weak"
    else:
        relevance_status = "strong"
    return RetrievalQualityResult(
        retrieved_documents=documents,
        query=query,
        retrieval_success=bool(documents),
        relevance_status=relevance_status,
        number_of_results=len(documents),
        best_distance=best_distance,
        average_distance=average_distance,
        whether_retry_was_used=retry_was_used,
        rewritten_query=rewritten_query,
    )


def _quality_rank(result: RetrievalQualityResult) -> tuple[int, float, int]:
    status_rank = {"strong": 2, "weak": 1, "no_results": 0}[result.relevance_status]
    distance = result.best_distance if result.best_distance is not None else float("inf")
    return status_rank, -distance, result.number_of_results


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
    logger.info(
        "RAG retrieval query=%r destination=%r collection=%r filters=%s",
        normalized_query,
        destination,
        getattr(knowledge_collection, "name", "travel_knowledge"),
        where,
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

    retrieved = [
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
    logger.info(
        "RAG retrieval results count=%d metadata=%s distances=%s",
        len(retrieved),
        [document.model_dump(exclude={"content"}) for document in retrieved],
        [document.distance for document in retrieved],
    )
    return retrieved


def retrieve_documents_with_quality(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    destination: str | None = None,
    category: str | None = None,
    document_type: str | None = None,
    *,
    collection=None,
    embedding_model: EmbeddingProvider | None = None,
    persist_directory: str | None = None,
    distance_threshold: float | None = None,
    max_attempts: int | None = None,
) -> RetrievalQualityResult:
    """Retrieve knowledge and retry once with a deterministic query rewrite when weak."""
    normalized_query = _validate_query(query)
    settings = get_rag_settings()
    threshold = settings.relevance_distance_threshold if distance_threshold is None else distance_threshold
    attempts_allowed = settings.max_retrieval_attempts if max_attempts is None else max_attempts
    if threshold < 0:
        raise ValueError("distance_threshold must be non-negative")
    if isinstance(attempts_allowed, bool) or not isinstance(attempts_allowed, int):
        raise ValueError("max_attempts must be an integer")
    if attempts_allowed < 1 or attempts_allowed > 2:
        raise ValueError("max_attempts must be between 1 and 2")

    first_documents = _deduplicate_documents(
        retrieve_documents(
            normalized_query,
            top_k=top_k,
            destination=destination,
            category=category,
            document_type=document_type,
            collection=collection,
            embedding_model=embedding_model,
            persist_directory=persist_directory,
        )
    )
    first_result = _quality_for(normalized_query, first_documents, threshold)
    if first_result.relevance_status == "strong" or attempts_allowed == 1:
        return first_result

    rewritten_query = _rewrite_query(normalized_query)
    retry_documents = _deduplicate_documents(
        retrieve_documents(
            rewritten_query,
            top_k=top_k,
            destination=destination,
            category=category,
            document_type=document_type,
            collection=collection,
            embedding_model=embedding_model,
            persist_directory=persist_directory,
        )
    )
    retry_result = _quality_for(
        normalized_query,
        retry_documents,
        threshold,
        retry_was_used=True,
        rewritten_query=rewritten_query,
    )
    if _quality_rank(retry_result) >= _quality_rank(first_result):
        return retry_result
    return first_result.model_copy(
        update={"whether_retry_was_used": True, "rewritten_query": rewritten_query}
    )
