from pathlib import Path

import chromadb
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import KnowledgeSource
from rag.chunking import PageText, chunk_pages
from rag.ingestion import chunk_id, document_id_for_path, extract_pdf_pages, ingest_pdf


class FakeEmbeddingModel:
    def encode(self, texts):
        return [[float(len(text)), 1.0] for text in texts]


def test_chunking_preserves_pages_and_overlap():
    pages = [PageText(1, "abcdefghij", "guide.pdf", "guide.pdf", "doc")]
    chunks = chunk_pages(pages, chunk_size=6, chunk_overlap=2)
    assert [chunk.text for chunk in chunks] == ["abcdef", "efghij"]
    assert [chunk.page for chunk in chunks] == [1, 1]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_pdf_extraction_and_invalid_inputs(tmp_path):
    sample = Path("test-data/Goa-Travel-Guide.pdf")
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(sample.read_bytes())
    pages = extract_pdf_pages(pdf, "doc")
    assert len(pages) == 5
    assert pages[0].page == 1
    assert pages[0].filename == "guide.pdf"
    assert pages[0].document_id == "doc"
    with pytest.raises(FileNotFoundError):
        extract_pdf_pages(tmp_path / "missing.pdf")
    txt = tmp_path / "guide.txt"
    txt.write_text("not a PDF", encoding="utf-8")
    with pytest.raises(ValueError, match="PDF"):
        extract_pdf_pages(txt)


def test_ingestion_indexes_and_reindexes_without_touching_preferences(tmp_path, monkeypatch):
    source_pdf = Path("test-data/Goa-Travel-Guide.pdf")
    pdf = tmp_path / source_pdf.name
    pdf.write_bytes(source_pdf.read_bytes())
    monkeypatch.setenv("RAG_CHUNK_SIZE", "500")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "60")
    chroma_path = tmp_path / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_path))
    preferences = client.get_or_create_collection("trip_preferences")
    preferences.add(ids=["preference-1"], documents=["prefers beaches"])

    db_engine = create_engine(f"sqlite:///{(tmp_path / 'rag.db').as_posix()}")
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        result = ingest_pdf(pdf, "Goa", "travel_guide", "destination_guide", db=db, persist_directory=str(chroma_path), embedding_model=FakeEmbeddingModel())
        again = ingest_pdf(pdf, "Goa", "travel_guide", "destination_guide", db=db, persist_directory=str(chroma_path), embedding_model=FakeEmbeddingModel())
        record = db.query(KnowledgeSource).one()

    knowledge = client.get_collection("travel_knowledge")
    stored = knowledge.get(include=["metadatas"])
    assert result["pages"] == 5
    assert result["chunks"] > 0
    assert result["status"] == "indexed"
    assert result == again
    assert len(stored["ids"]) == result["chunks"]
    assert all(metadata["destination"] == "Goa" for metadata in stored["metadatas"])
    assert all(metadata["category"] == "travel_guide" and metadata["document_type"] == "destination_guide" for metadata in stored["metadatas"])
    assert all(metadata["filename"] == source_pdf.name and metadata["page"] >= 1 for metadata in stored["metadatas"])
    assert all(item.startswith(result["document_id"] + ":") for item in stored["ids"])
    assert document_id_for_path(pdf) == result["document_id"]
    assert chunk_id(result["document_id"], 1, 0) in stored["ids"]
    assert record.page_count == 5
    assert record.chunk_count == result["chunks"]
    assert record.status == "indexed"
    assert preferences.count() == 1