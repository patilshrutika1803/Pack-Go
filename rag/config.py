import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RagSettings:
    collection_name: str = "travel_knowledge"
    chunk_size: int = 500
    chunk_overlap: int = 60
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_path: str = "./chroma_db"


def get_rag_settings() -> RagSettings:
    return RagSettings(
        collection_name=os.getenv("RAG_COLLECTION_NAME", "travel_knowledge"),
        chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "500")),
        chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "60")),
        embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        chroma_path=os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db"),
    )