from __future__ import annotations

import getpass
from uuid import uuid4

from sqlalchemy import select

from database import User
from database.connection import SessionLocal
from services.auth_service import AuthService


def _password(prompt: str) -> str:
    password = getpass.getpass(prompt)
    if len(password) < 8 or not password.strip():
        raise ValueError("Password must be at least 8 characters long.")
    return password


def main() -> None:
    email = input("Admin email: ").strip().lower()
    if not email:
        raise ValueError("Email is required.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            name = input("Admin name: ").strip()
            if not name:
                raise ValueError("Name is required for a new user.")
            password = _password("Password: ")
            confirmation = _password("Confirm password: ")
            if password != confirmation:
                raise ValueError("Passwords do not match.")
            service = AuthService()
            user = User(
                id=str(uuid4()),
                name=name,
                email=email,
                password_hash=service._hash_password(password),
                is_admin=True,
            )
            db.add(user)
            action = "Created admin account"
        else:
            user.is_admin = True
            action = "Promoted existing account to admin"
        db.commit()

    print(f"{action}: {email}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc