import hashlib
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy.orm import Session

from database.models import KnowledgeSource
from logger.logging import get_logger
from rag.chunking import PageText, chunk_pages
from rag.config import get_rag_settings
from rag.embeddings import EmbeddingProvider, embed_texts
from rag.vector_store import get_knowledge_collection, replace_document_chunks

logger = get_logger(__name__)


def document_id_for_path(pdf_path: str | Path) -> str:
    return hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()


def chunk_id(document_id: str, page: int, chunk_index: int) -> str:
    return f"{document_id}:{page}:{chunk_index}"


def extract_pdf_pages(pdf_path: str | Path, document_id: str | None = None) -> list[PageText]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Knowledge sources must be PDF files")
    resolved_document_id = document_id or document_id_for_path(path)
    try:
        reader = PdfReader(str(path))
        return [PageText(index + 1, page.extract_text() or "", path.name, path.name, resolved_document_id) for index, page in enumerate(reader.pages)]
    except Exception as exc:
        logger.exception("Could not extract PDF %s", path)
        raise ValueError("Could not read PDF document") from exc


def ingest_pdf(pdf_path: str | Path, destination: str, category: str, document_type: str, db: Session | None = None, persist_directory: str | None = None, embedding_model: EmbeddingProvider | None = None, display_name: str | None = None) -> dict:
    path = Path(pdf_path)
    document_id = document_id_for_path(path)
    pages = extract_pdf_pages(path, document_id)
    settings = get_rag_settings()
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("PDF document contains no extractable text")
    texts = [item.text for item in chunks]
    embeddings = embed_texts(texts, embedding_model)
    metadatas = [{"document_id": document_id, "source": item.source, "filename": item.filename, "page": item.page, "chunk_index": item.chunk_index, "destination": destination, "category": category, "document_type": document_type} for item in chunks]
    ids = [chunk_id(document_id, item.page, item.chunk_index) for item in chunks]
    collection = get_knowledge_collection(persist_directory=persist_directory)
    replace_document_chunks(collection, document_id, texts, embeddings, metadatas, ids)
    if db is not None:
        source = db.query(KnowledgeSource).filter_by(document_id=document_id).one_or_none()
        if source is None:
            source = KnowledgeSource(id=str(uuid4()), document_id=document_id, filename=path.name, display_name=display_name or path.name, destination=destination, category=category, document_type=document_type, file_path=str(path), chunk_count=len(chunks), page_count=len(pages), status="indexed")
            db.add(source)
        else:
            source.filename, source.display_name, source.destination = path.name, display_name or path.name, destination
            source.category, source.document_type, source.file_path = category, document_type, str(path)
            source.chunk_count, source.page_count, source.status = len(chunks), len(pages), "indexed"
        db.commit()
    result = {"document_id": document_id, "filename": path.name, "pages": len(pages), "chunks": len(chunks), "collection": settings.collection_name, "status": "indexed"}
    logger.info("Indexed %s: %s pages, %s chunks", path.name, len(pages), len(chunks))
    return result