from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent.knowledge_agent import knowledge_agent_node
from api.v1.dependencies import get_current_admin, get_current_user
from database import KnowledgeSource, User
from database.connection import get_db
from rag.ingestion import ingest_pdf
from rag.vector_store import get_knowledge_collection


router = APIRouter(prefix="/api/v1/admin/knowledge", tags=["Admin Knowledge"])
user_router = APIRouter(prefix="/api/v1/knowledge", tags=["User Knowledge"])
MAX_UPLOAD_BYTES = int(os.getenv("RAG_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,254}\.pdf$", re.IGNORECASE)


class KnowledgeAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    destination: str | None = None
    category: str | None = None
    document_type: str | None = None


def _storage_root() -> Path:
    root = Path(os.getenv("RAG_STORAGE_DIRECTORY", "./knowledge_storage")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_filename(filename: str | None) -> str:
    safe_name = Path(filename or "").name
    if safe_name != (filename or "") or not FILENAME_PATTERN.fullmatch(safe_name):
        raise HTTPException(status_code=422, detail="A safe PDF filename is required.")
    return safe_name


def _serialize(source: KnowledgeSource) -> dict:
    return {
        "id": source.id,
        "document_id": source.document_id,
        "filename": source.filename,
        "display_name": source.display_name,
        "destination": source.destination,
        "category": source.category,
        "document_type": source.document_type,
        "chunk_count": source.chunk_count,
        "page_count": source.page_count,
        "status": source.status,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _serialize_user(source: KnowledgeSource) -> dict:
    return {
        "id": source.id,
        "document_id": source.document_id,
        "filename": source.filename,
        "display_name": source.display_name,
        "destination": source.destination,
        "category": source.category,
        "document_type": source.document_type,
        "chunk_count": source.chunk_count,
        "page_count": source.page_count,
        "status": source.status,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _require_metadata(display_name: str, destination: str, category: str, document_type: str) -> None:
    if any(not value.strip() for value in (display_name, destination, category, document_type)):
        raise HTTPException(status_code=422, detail="Document metadata is required.")


@user_router.get("")
def list_user_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = None,
    destination: str | None = None,
    category: str | None = None,
    document_type: str | None = None,
):
    query = db.query(KnowledgeSource)
    if search:
        query = query.filter(KnowledgeSource.display_name.ilike(f"%{search.strip()}%"))
    for field, value in ((KnowledgeSource.destination, destination), (KnowledgeSource.category, category), (KnowledgeSource.document_type, document_type)):
        if value:
            query = query.filter(field == value)
    return [_serialize_user(source) for source in query.order_by(KnowledgeSource.created_at.desc()).all()]


@user_router.post("/ask")
def ask_user_knowledge(
    request: KnowledgeAskRequest,
    _: User = Depends(get_current_user),
):
    result = knowledge_agent_node(
        {
            "query": request.question,
            "knowledge_destination": request.destination,
            "knowledge_category": request.category,
            "knowledge_document_type": request.document_type,
        }
    )
    answer = result.get("knowledge_answer")
    if answer is None:
        raise HTTPException(status_code=503, detail=result.get("knowledge_failure", "Knowledge retrieval is unavailable."))
    return answer.model_dump(mode="json")


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    display_name: str = Form(...),
    destination: str = Form(...),
    category: str = Form(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    filename = _validate_filename(file.filename)
    if file.content_type not in (None, "application/pdf"):
        raise HTTPException(status_code=415, detail="Only PDF documents are supported.")
    _require_metadata(display_name, destination, category, document_type)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the configured size limit.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid PDF.")

    path = _storage_root() / f"{uuid4()}-{filename}"
    path.write_bytes(content)
    try:
        result = ingest_pdf(
            path,
            destination=destination.strip(),
            category=category.strip(),
            document_type=document_type.strip(),
            display_name=display_name.strip(),
            db=db,
        )
        source = db.query(KnowledgeSource).filter_by(document_id=result["document_id"]).one()
        return _serialize(source)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="The PDF could not be indexed.") from exc


@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
    search: str | None = None,
    destination: str | None = None,
    category: str | None = None,
    document_type: str | None = None,
):
    query = db.query(KnowledgeSource)
    if search:
        query = query.filter(KnowledgeSource.display_name.ilike(f"%{search.strip()}%"))
    for field, value in ((KnowledgeSource.destination, destination), (KnowledgeSource.category, category), (KnowledgeSource.document_type, document_type)):
        if value:
            query = query.filter(field == value)
    return [_serialize(source) for source in query.order_by(KnowledgeSource.created_at.desc()).all()]


@router.get("/documents/{source_id}")
def get_document(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    source = db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return _serialize(source)


@router.post("/documents/{source_id}/reindex")
def reindex_document(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    source = db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    path = Path(source.file_path).resolve()
    if path.parent != _storage_root() or not path.is_file():
        raise HTTPException(status_code=422, detail="Stored source file is unavailable.")
    source.status = "processing"
    db.commit()
    try:
        result = ingest_pdf(path, source.destination, source.category, source.document_type, db=db, display_name=source.display_name)
        return _serialize(db.query(KnowledgeSource).filter_by(document_id=result["document_id"]).one())
    except Exception as exc:
        source.status = "failed"
        db.commit()
        raise HTTPException(status_code=422, detail="The document could not be re-indexed.") from exc


@router.delete("/documents/{source_id}")
def delete_document(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    source = db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    collection = get_knowledge_collection()
    collection.delete(where={"document_id": source.document_id})
    path = Path(source.file_path).resolve()
    if path.parent == _storage_root():
        path.unlink(missing_ok=True)
    db.delete(source)
    db.commit()
    return {"message": "Knowledge document deleted."}