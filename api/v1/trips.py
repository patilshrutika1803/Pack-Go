from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from database.connection import get_db
from database.models import Trip
from database import User
from api.v1.dependencies import get_current_user
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
def create_trip(payload: TripCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripResponse:
    _ = db
    trip_service = TripService(db)

    trip = Trip(**payload.model_dump(exclude_none=True), user_id=user.id)
    created_trip = trip_service.create_trip(trip)
    return TripResponse.model_validate(created_trip)


@router.get("/trips", response_model=list[TripResponse])
def list_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[TripResponse]:
    trips = TripAccessService(db).list_trips_for_user(user.id)
    return [TripResponse.model_validate(trip) for trip in trips]


@router.get("/trips/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripResponse:
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    return TripResponse.model_validate(trip)


@router.patch("/trips/{trip_id}", response_model=TripResponse)
def update_trip(trip_id: str, payload: TripUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripResponse:
    trip_service = TripService(db)
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)

    if not updates:
        try:
            trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
            TripAccessService(db).require_can_edit_trip(trip_id, user.id)
        except AccessDenied:
            _raise_trip_not_found()
        return TripResponse.model_validate(trip)

    try:
        TripAccessService(db).require_can_edit_trip(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    updated_trip = trip_service.update_trip(trip_id, updates)
    if updated_trip is None:
        _raise_trip_not_found()

    return TripResponse.model_validate(updated_trip)


@router.patch(
    "/trips/{trip_id}/days/{day_number}/regenerate",
    response_model=TripDayRegenerationResponse,
)
def regenerate_trip_day(
    trip_id: str,
    day_number: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TripDayRegenerationResponse:
    trip_service = TripService(db)

    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
        TripAccessService(db).require_can_edit_trip(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()

    try:
        result = trip_service.regenerate_day(trip_id, day_number)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.") from exc
    except DayNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Day {day_number} not found for trip {trip_id}.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate the travel plan at this time. Please try again.",
        ) from exc

    return TripDayRegenerationResponse.model_validate(result)


@router.delete("/trips/{trip_id}", response_model=DeleteTripResponse)
def delete_trip(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DeleteTripResponse:
    try:
        TripAccessService(db).require_owner(trip_id, user.id)
    except AccessDenied:
        _raise_trip_not_found()
    trip_service = TripService(db)
    deleted = trip_service.delete_trip(trip_id)
    if not deleted:
        _raise_trip_not_found()
    return DeleteTripResponse(message="Trip deleted successfully.")
