from __future__ import annotations

import os
from datetime import UTC, datetime
from threading import Lock

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pymongo.database import Database
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError, AuthRetryableError

from database.mongodb import get_database

bearer = HTTPBearer(auto_error=False)
_supabase: Client | None = None
_supabase_lock = Lock()


class CurrentUser(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool = True
    is_verified: bool = False
    is_admin: bool = False


def _get_supabase_client() -> Client:
    global _supabase
    if _supabase is not None:
        return _supabase
    with _supabase_lock:
        if _supabase is not None:
            return _supabase
        url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url:
            raise RuntimeError("SUPABASE_URL must be configured.")
        if not service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY must be configured on the backend.")
        _supabase = create_client(url, service_role_key)
        return _supabase


def _profile_for_token(token: str, database: Database) -> CurrentUser:
    try:
        response = _get_supabase_client().auth.get_user(token)
    except AuthApiError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.") from exc
    except AuthRetryableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication provider is temporarily unavailable.") from exc

    identity = response.user if response else None
    if identity is None or not identity.id or not identity.email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    existing = database.users.find_one(
        {"_id": identity.id},
        {"is_admin": 1, "is_active": 1, "created_at": 1},
    )
    if existing and existing.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
    metadata = identity.user_metadata or {}
    name = metadata.get("name") or metadata.get("full_name") or identity.email.split("@", 1)[0]
    now = datetime.now(UTC)
    profile = {
        "_id": identity.id,
        "id": identity.id,
        "supabase_user_id": identity.id,
        "name": name,
        "email": identity.email.lower(),
        "is_active": existing.get("is_active", True) if existing else True,
        "is_verified": bool(identity.email_confirmed_at),
        "is_admin": bool(existing and existing.get("is_admin", False)),
        "created_at": existing.get("created_at", now) if existing else now,
        "updated_at": now,
    }
    database.users.update_one(
        {"_id": identity.id},
        {"$set": {key: value for key, value in profile.items() if key not in {"_id", "id", "created_at", "is_admin"}},
         "$setOnInsert": {"id": identity.id, "created_at": now, "is_admin": False}},
        upsert=True,
    )
    profile["is_admin"] = bool(existing and existing.get("is_admin", False))
    return CurrentUser.model_validate(profile)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    database: Database = Depends(get_database),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return _profile_for_token(credentials.credentials, database)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    database: Database = Depends(get_database),
) -> CurrentUser | None:
    if credentials is None:
        return None
    return _profile_for_token(credentials.credentials, database)


def get_current_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required.")
    return user
