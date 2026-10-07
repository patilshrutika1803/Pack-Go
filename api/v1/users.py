from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.database import Database

from api.v1.dependencies import CurrentUser, get_current_user
from database.mongodb import get_database
from models.api_schemas import PreferenceResponse, PreferenceUpdateRequest

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

_PREFERENCE_DEFAULTS = {
    "travel_style": None,
    "interests": [],
    "things_to_avoid": [],
    "budget_preference": None,
    "hotel_preference": None,
    "food_preference": None,
    "preferred_destinations": [],
    "preferred_budget_min": None,
    "preferred_budget_max": None,
    "preferred_currency": "INR",
    "preferred_trip_duration": None,
    "is_domestic": None,
}


class ProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool
    is_verified: bool
    is_admin: bool = False


@router.get("/me", response_model=ProfileResponse)
def current_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


def _preference_response(user_id: str, preferences: dict) -> PreferenceResponse:
    return PreferenceResponse(id=f"{user_id}:preferences", user_id=user_id, **preferences)


@router.get("/me/preferences", response_model=PreferenceResponse)
def get_preferences(
    user: CurrentUser = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> PreferenceResponse:
    stored = database.users.find_one({"_id": user.id}, {"preferences": 1}) or {}
    preferences = stored.get("preferences") or {}
    if not preferences:
        preferences = dict(_PREFERENCE_DEFAULTS)
        database.users.update_one({"_id": user.id}, {"$set": {"preferences": preferences}})
    return _preference_response(user.id, {**_PREFERENCE_DEFAULTS, **preferences})


@router.patch("/me/preferences", response_model=PreferenceResponse)
def update_preferences(
    payload: PreferenceUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> PreferenceResponse:
    updates = payload.model_dump(exclude_unset=True)
    now = datetime.now(UTC)
    operations = {f"preferences.{key}": value for key, value in updates.items()}
    operations["preferences.updated_at"] = now
    database.users.update_one(
        {"_id": user.id},
        {"$set": operations},
        upsert=True,
    )
    stored = database.users.find_one({"_id": user.id}, {"preferences": 1}) or {}
    preferences = {**_PREFERENCE_DEFAULTS, **(stored.get("preferences") or {})}
    return _preference_response(user.id, preferences)
