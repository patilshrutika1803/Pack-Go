from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from api.v1.dependencies import CurrentUser, get_current_user
from database.mongodb import get_database
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
    raise exc


@router.get("/trips/{trip_id}/journal", response_model=list[JournalEntryResponse])
def list_journal_entries(
    trip_id: str,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return [JournalEntryResponse.model_validate(entry) for entry in JournalService(database).list_entries(trip_id, user.id)]
    except AccessDenied as exc:
        _handle_error(exc)


@router.post("/trips/{trip_id}/journal", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    trip_id: str,
    payload: JournalEntryCreateRequest,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        entry = JournalService(database).create(trip_id, user.id, payload.model_dump())
        return JournalEntryResponse.model_validate(entry)
    except (AccessDenied, ValueError) as exc:
        _handle_error(exc)


@router.patch("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
def update_journal_entry(
    entry_id: str,
    payload: JournalEntryUpdateRequest,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        entry = JournalService(database).update(entry_id, user.id, payload.model_dump(exclude_unset=True))
        return JournalEntryResponse.model_validate(entry)
    except (AccessDenied, ValueError) as exc:
        _handle_error(exc)


@router.delete("/journal-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_entry(
    entry_id: str,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        JournalService(database).delete(entry_id, user.id)
    except AccessDenied as exc:
        _handle_error(exc)


@router.get("/trips/{trip_id}/journal/statistics", response_model=TripJournalStatisticsResponse)
def journal_statistics(
    trip_id: str,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return JournalService(database).statistics(trip_id, user.id)
    except AccessDenied as exc:
        _handle_error(exc)
