from __future__ import annotations

from typing import Any

from logger.logging import get_logger
from rag.generation import GroundedAnswer, generate_grounded_answer
from rag.retrieval import RetrievalQualityResult, retrieve_documents_with_quality


logger = get_logger(__name__)


KNOWLEDGE_TERMS = {
    "accommodation",
    "attraction",
    "beach",
    "beaches",
    "capital",
    "destination",
    "guide",
    "reach",
    "season",
    "seasons",
    "safety",
    "transport",
    "travel",
    "tips",
    "things",
    "visit",
    "visits",
    "activities",
    "food",
    "culture",
}


def is_knowledge_query(query: str) -> bool:
    normalized_query = " ".join(query.split()).lower()
    if not normalized_query or "pack & go" in normalized_query:
        return False
    if normalized_query in {"hello", "hi", "hey", "what can you do?"}:
        return False
    words = set(normalized_query.replace("?", " ").replace("-", " ").split())
    return bool(words & KNOWLEDGE_TERMS)


def knowledge_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve and ground a knowledge-base answer without replacing ResearchAgent."""
    query = str(state.get("query", "")).strip()
    if not query:
        return {
            "knowledge_answer": None,
            "knowledge_documents": [],
            "knowledge_failure": "Knowledge query is unavailable.",
        }
    try:
        quality: RetrievalQualityResult = retrieve_documents_with_quality(
            query,
            destination=state.get("knowledge_destination"),
            category=state.get("knowledge_category"),
            document_type=state.get("knowledge_document_type"),
        )
        answer: GroundedAnswer = generate_grounded_answer(
            query,
            quality.retrieved_documents,
            retrieval_status=quality.relevance_status,
        )
        return {
            "knowledge_answer": answer,
            "knowledge_documents": quality.retrieved_documents,
            "knowledge_retrieval": quality,
            "completed_agents": ["KnowledgeAgent"],
        }
    except Exception:
        logger.exception("KnowledgeAgent failed for query")
        return {
            "knowledge_answer": None,
            "knowledge_documents": [],
            "knowledge_failure": "Knowledge retrieval is unavailable.",
            "failed_agents": ["KnowledgeAgent"],
        }