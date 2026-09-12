import chromadb

from rag.config import get_rag_settings


def get_chroma_client(persist_directory: str | None = None):
    return chromadb.PersistentClient(path=persist_directory or get_rag_settings().chroma_path)


def get_knowledge_collection(client=None, persist_directory: str | None = None):
    client = client or get_chroma_client(persist_directory)
    return client.get_or_create_collection(name=get_rag_settings().collection_name)


def replace_document_chunks(collection, document_id: str, chunks: list[str], embeddings: list[list[float]], metadatas: list[dict], ids: list[str]) -> None:
    collection.delete(where={"document_id": document_id})
    if chunks:
        collection.add(documents=chunks, embeddings=embeddings, metadatas=metadatas, ids=ids)