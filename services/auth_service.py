from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import User


class AuthError(Exception):
    """Expected authentication failure."""


class AuthService:
    def __init__(self, secret: str | None = None):
        self.secret = secret or os.getenv("PACK_GO_JWT_SECRET")
        if not self.secret or len(self.secret) < 32:
            raise RuntimeError("PACK_GO_JWT_SECRET must be configured with at least 32 characters.")

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _public_user(user: User) -> dict[str, object]:
        return {"id": user.id, "name": user.name, "email": user.email, "is_active": user.is_active, "is_verified": user.is_verified}

    def register(self, db: Session, name: str, email: str, password: str) -> dict[str, object]:
        normalized_email = self._normalize_email(email)
        if db.scalar(select(User).where(User.email == normalized_email)):
            raise AuthError("An account with that email already exists.")
        user = User(id=str(uuid4()), name=name.strip(), email=normalized_email, password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
        db.add(user)
        db.commit()
        db.refresh(user)
        return self._tokens(user)

    def login(self, db: Session, email: str, password: str) -> dict[str, object]:
        user = db.scalar(select(User).where(User.email == self._normalize_email(email)))
        if not user or not user.is_active or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            raise AuthError("The email or password is incorrect.")
        return self._tokens(user)

    def _tokens(self, user: User) -> dict[str, object]:
        now = datetime.now(UTC)
        access = jwt.encode({"sub": user.id, "type": "access", "exp": now + timedelta(minutes=30)}, self.secret, algorithm="HS256")
        refresh = jwt.encode({"sub": user.id, "type": "refresh", "exp": now + timedelta(days=30)}, self.secret, algorithm="HS256")
        return {"access_token": access, "refresh_token": refresh, "user": self._public_user(user)}