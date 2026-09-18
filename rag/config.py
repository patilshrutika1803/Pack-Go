import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RagSettings:
    collection_name: str = "travel_knowledge"
    chunk_size: int = 500
    chunk_overlap: int = 60
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_path: str = "./chroma_db"
    relevance_distance_threshold: float = 0.75
    max_retrieval_attempts: int = 2


def get_rag_settings() -> RagSettings:
    configured_chroma_path = os.getenv("CHROMA_PERSIST_DIRECTORY")
    chroma_path = Path(configured_chroma_path) if configured_chroma_path else PROJECT_ROOT / "chroma_db"
    if not chroma_path.is_absolute():
        chroma_path = PROJECT_ROOT / chroma_path
    return RagSettings(
        collection_name=os.getenv("RAG_COLLECTION_NAME", "travel_knowledge"),
        chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "500")),
        chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "60")),
        embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        chroma_path=str(chroma_path),
        relevance_distance_threshold=float(os.getenv("RAG_RELEVANCE_DISTANCE_THRESHOLD", "0.75")),
        max_retrieval_attempts=min(int(os.getenv("RAG_MAX_RETRIEVAL_ATTEMPTS", "2")), 2),
    )