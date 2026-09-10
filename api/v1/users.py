from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.dependencies import get_current_user
from database import User, UserPreference
from database.connection import get_db
from models.api_schemas import PreferenceResponse, PreferenceUpdateRequest, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/me/preferences", response_model=PreferenceResponse)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPreference:
    preferences = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if preferences is None:
        preferences = UserPreference(id=str(uuid4()), user_id=user.id, interests=[], things_to_avoid=[])
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    return preferences


@router.patch("/me/preferences", response_model=PreferenceResponse)
def update_preferences(payload: PreferenceUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPreference:
    preferences = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if preferences is None:
        preferences = UserPreference(id=str(uuid4()), user_id=user.id, interests=[], things_to_avoid=[])
        db.add(preferences)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(preferences, key, value)
    db.commit()
    db.refresh(preferences)
    return preferences
