from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.v1.dependencies import get_current_user
from database import User
from database.connection import get_db
from models.api_schemas import (
    JournalEntryCreateRequest,
    JournalEntryResponse,
    JournalEntryUpdateRequest,
    TripJournalStatisticsResponse,
)
from services.collaboration_service import AccessDenied
from services.journal_service import JournalService

router = APIRouter(prefix="/api/v1", tags=["Travel Journal"])


def _handle_error(exc: Exception):
    if isinstance(exc, AccessDenied):
        not_found = str(exc) in {"Trip not found.", "Journal entry not found."}
        raise HTTPException(status_code=404 if not_found else 403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=500, detail="Unable to save journal data at this time.") from exc
    raise exc


def _entry_response(entry):
    return JournalEntryResponse(
        id=entry.id,
        trip_id=entry.trip_id,
        created_by_user_id=entry.created_by_user_id,
        author_name=entry.author.name,
        title=entry.title,
        content=entry.content,
        occurred_at=entry.occurred_at,
        media_references=entry.media_references,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/trips/{trip_id}/journal", response_model=list[JournalEntryResponse])
def list_journal_entries(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return [_entry_response(entry) for entry in JournalService(db).list_entries(trip_id, user.id)]
    except AccessDenied as exc:
        _handle_error(exc)


@router.post("/trips/{trip_id}/journal", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_journal_entry(trip_id: str, payload: JournalEntryCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        entry = JournalService(db).create(trip_id, user.id, payload.model_dump())
        return _entry_response(entry)
    except (AccessDenied, ValueError, RuntimeError) as exc:
        _handle_error(exc)


@router.patch("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
def update_journal_entry(entry_id: str, payload: JournalEntryUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        entry = JournalService(db).update(entry_id, user.id, payload.model_dump(exclude_unset=True))
        return _entry_response(entry)
    except (AccessDenied, ValueError, RuntimeError) as exc:
        _handle_error(exc)


@router.delete("/journal-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_entry(entry_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        JournalService(db).delete(entry_id, user.id)
    except (AccessDenied, RuntimeError) as exc:
        _handle_error(exc)


@router.get("/trips/{trip_id}/journal/statistics", response_model=TripJournalStatisticsResponse)
def journal_statistics(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return JournalService(db).statistics(trip_id, user.id)
    except AccessDenied as exc:
        _handle_error(exc)