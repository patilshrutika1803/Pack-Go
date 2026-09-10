from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import PasswordResetToken, RefreshToken, User, VerificationToken


class AuthError(Exception):
    """Expected authentication failure."""


class AuthService:
    ACCESS_MINUTES = 15
    REFRESH_DAYS = 30
    VERIFICATION_HOURS = 24
    RESET_MINUTES = 30

    def __init__(self, secret: str | None = None):
        self.secret = secret or os.getenv("PACK_GO_JWT_SECRET")
        if not self.secret or len(self.secret) < 32:
            raise RuntimeError("PACK_GO_JWT_SECRET must be configured with at least 32 characters.")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _public_user(user: User) -> dict[str, object]:
        return {"id": user.id, "name": user.name, "email": user.email, "is_active": user.is_active, "is_verified": user.is_verified}

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _dev_mode() -> bool:
        return os.getenv("PACK_GO_ENV", "development").lower() != "production"

    def register(self, db: Session, name: str, email: str, password: str) -> dict[str, object]:
        normalized_email = self._normalize_email(email)
        if len(password) < 8 or not password.strip():
            raise AuthError("Password must be at least 8 characters long.")
        if db.scalar(select(User).where(User.email == normalized_email)):
            raise AuthError("An account with this email already exists.")
        user = User(id=str(uuid4()), name=name.strip(), email=normalized_email, password_hash=self._hash_password(password))
        db.add(user)
        db.flush()
        verification_token = self._create_verification_token(db, user)
        result = self._tokens(db, user)
        db.commit()
        db.refresh(user)
        result["user"] = self._public_user(user)
        if self._dev_mode():
            result["verification_token"] = verification_token
        return result

    def login(self, db: Session, email: str, password: str) -> dict[str, object]:
        user = db.scalar(select(User).where(User.email == self._normalize_email(email)))
        if not user or not user.is_active or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            raise AuthError("The email or password is incorrect.")
        result = self._tokens(db, user)
        db.commit()
        return result

    def _tokens(self, db: Session, user: User) -> dict[str, object]:
        now = self._now()
        access = jwt.encode({"sub": user.id, "type": "access", "exp": now + timedelta(minutes=self.ACCESS_MINUTES)}, self.secret, algorithm="HS256")
        refresh_id = str(uuid4())
        refresh = jwt.encode({"sub": user.id, "jti": refresh_id, "type": "refresh", "exp": now + timedelta(days=self.REFRESH_DAYS)}, self.secret, algorithm="HS256")
        db.add(RefreshToken(id=refresh_id, user_id=user.id, token_hash=self._token_hash(refresh), expires_at=now + timedelta(days=self.REFRESH_DAYS)))
        return {"access_token": access, "refresh_token": refresh, "user": self._public_user(user)}

    def refresh(self, db: Session, refresh_token: str) -> dict[str, object]:
        try:
            payload = jwt.decode(refresh_token, self.secret, algorithms=["HS256"])
            token_id = payload.get("jti")
            if payload.get("type") != "refresh" or not token_id:
                raise AuthError("Invalid refresh token.")
        except (jwt.PyJWTError, AuthError) as exc:
            raise AuthError("Invalid refresh token.") from exc
        stored = db.scalar(select(RefreshToken).where(RefreshToken.id == token_id, RefreshToken.token_hash == self._token_hash(refresh_token)))
        now = self._now()
        if not stored or stored.revoked_at or self._as_utc(stored.expires_at) <= now:
            raise AuthError("Invalid refresh token.")
        user = db.get(User, stored.user_id)
        if not user or not user.is_active:
            raise AuthError("Invalid refresh token.")
        stored.revoked_at = now
        result = self._tokens(db, user)
        new_payload = jwt.decode(result["refresh_token"], self.secret, algorithms=["HS256"])
        stored.replaced_by = new_payload["jti"]
        db.commit()
        return result

    def logout(self, db: Session, refresh_token: str) -> None:
        try:
            payload = jwt.decode(refresh_token, self.secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return
        if payload.get("type") != "refresh" or not payload.get("jti"):
            return
        stored = db.scalar(select(RefreshToken).where(RefreshToken.id == payload["jti"], RefreshToken.token_hash == self._token_hash(refresh_token)))
        if stored and not stored.revoked_at:
            stored.revoked_at = self._now()
            db.commit()

    def current_user(self, db: Session, access_token: str) -> User:
        try:
            payload = jwt.decode(access_token, self.secret, algorithms=["HS256"])
            if payload.get("type") != "access" or not payload.get("sub"):
                raise AuthError("Invalid access token.")
        except (jwt.PyJWTError, AuthError) as exc:
            raise AuthError("Invalid access token.") from exc
        user = db.get(User, payload["sub"])
        if not user or not user.is_active:
            raise AuthError("Invalid access token.")
        return user

    def _create_verification_token(self, db: Session, user: User) -> str:
        raw = secrets.token_urlsafe(32)
        now = self._now()
        db.add(VerificationToken(id=str(uuid4()), user_id=user.id, token_hash=self._token_hash(raw), expires_at=now + timedelta(hours=self.VERIFICATION_HOURS)))
        return raw

    def verify_email(self, db: Session, raw_token: str) -> User:
        token = db.scalar(select(VerificationToken).where(VerificationToken.token_hash == self._token_hash(raw_token)))
        if not token or token.used_at or self._as_utc(token.expires_at) <= self._now():
            raise AuthError("Invalid verification token.")
        user = db.get(User, token.user_id)
        if not user:
            raise AuthError("Invalid verification token.")
        user.is_verified = True
        token.used_at = self._now()
        db.commit()
        return user

    def forgot_password(self, db: Session, email: str) -> str | None:
        user = db.scalar(select(User).where(User.email == self._normalize_email(email)))
        if not user:
            return None
        raw = secrets.token_urlsafe(32)
        now = self._now()
        db.add(PasswordResetToken(id=str(uuid4()), user_id=user.id, token_hash=self._token_hash(raw), expires_at=now + timedelta(minutes=self.RESET_MINUTES)))
        db.commit()
        return raw

    def reset_password(self, db: Session, raw_token: str, password: str) -> None:
        if len(password) < 8 or not password.strip():
            raise AuthError("Password must be at least 8 characters long.")
        token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == self._token_hash(raw_token)))
        if not token or token.used_at or self._as_utc(token.expires_at) <= self._now():
            raise AuthError("Invalid password reset token.")
        user = db.get(User, token.user_id)
        if not user:
            raise AuthError("Invalid password reset token.")
        user.password_hash = self._hash_password(password)
        token.used_at = self._now()
        for refresh in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))):
            refresh.revoked_at = self._now()
        db.commit()
