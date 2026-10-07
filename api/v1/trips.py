from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from api.v1.dependencies import CurrentUser, get_current_user
from database.mongodb import get_database
from models.api_schemas import (
    DeleteTripResponse,
    TripCreateRequest,
    TripDayRegenerationResponse,
    TripResponse,
    TripUpdateRequest,
)
from services.trip_service import DayNotFoundError, TripNotFoundError, TripService
from services.collaboration_service import AccessDenied, TripAccessService

router = APIRouter(prefix="/api/v1", tags=["Trips"])


def _raise_trip_not_found() -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.")


@router.post("/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreateRequest,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> TripResponse:
    trip_document = payload.model_dump(exclude_none=True)
    trip_document["user_id"] = user.id
    trip = TripService(database).create_trip(trip_document, trip_id=trip_document.get("id"))
    return TripResponse.model_validate(trip)


@router.get("/trips", response_model=list[TripResponse])
def list_trips(
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> list[TripResponse]:
    trips = TripAccessService(database).list_trips_for_user(user.id)
    return [TripResponse.model_validate(trip) for trip in trips]


@router.get("/trips/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: str,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> TripResponse:
    try:
        trip = TripAccessService(database).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    return TripResponse.model_validate(trip)


@router.patch("/trips/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: str,
    payload: TripUpdateRequest,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> TripResponse:
    service = TripService(database)
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    access = TripAccessService(database)
    if not updates:
        try:
            trip = access.get_trip_for_member(trip_id, user.id)
            access.require_can_edit_trip(trip_id, user.id)
        except AccessDenied:
            _raise_trip_not_found()
        return TripResponse.model_validate(trip)

    try:
        access.require_can_edit_trip(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    updated = service.update_trip(trip_id, updates)
    if updated is None:
        _raise_trip_not_found()
    return TripResponse.model_validate(updated)


@router.patch("/trips/{trip_id}/days/{day_number}/regenerate", response_model=TripDayRegenerationResponse)
def regenerate_trip_day(
    trip_id: str,
    day_number: int,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> TripDayRegenerationResponse:
    access = TripAccessService(database)
    try:
        access.get_trip_for_member(trip_id, user.id)
        access.require_can_edit_trip(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    try:
        result = TripService(database).regenerate_day(trip_id, day_number)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.") from exc
    except DayNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Day {day_number} not found for trip {trip_id}.") from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate the travel plan at this time. Please try again.",
        ) from exc
    return TripDayRegenerationResponse.model_validate(result)


@router.delete("/trips/{trip_id}", response_model=DeleteTripResponse)
def delete_trip(
    trip_id: str,
    database: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> DeleteTripResponse:
    try:
        TripAccessService(database).require_can_delete_trip(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    if not TripService(database).delete_trip(trip_id):
        _raise_trip_not_found()
    return DeleteTripResponse(message="Trip deleted successfully.")
