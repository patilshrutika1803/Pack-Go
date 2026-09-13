import importlib

import bcrypt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    db_file = tmp_path / "auth.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")
    import database.connection as connection_module
    import database as database_module
    connection_module = importlib.reload(connection_module)
    importlib.reload(database_module)
    from database.base import Base
    Base.metadata.create_all(bind=connection_module.engine)
    import main as main_module
    main_module = importlib.reload(main_module)
    return TestClient(main_module.app, raise_server_exceptions=False)


def register(client, email):
    response = client.post("/api/v1/auth/register", json={"name": "A Traveler", "email": email, "password": "password123"})
    assert response.status_code == 201
    return response.json()


def auth_header(payload):
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_registration_login_current_user_and_duplicate_email(auth_client):
    result = register(auth_client, "traveler@example.com")
    assert result["user"]["is_verified"] is False
    assert auth_client.get("/api/v1/users/me", headers=auth_header(result)).json()["email"] == "traveler@example.com"
    duplicate = auth_client.post("/api/v1/auth/register", json={"name": "Other", "email": "TRAVELER@example.com", "password": "password123"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == "An account with this email already exists."
    invalid_login = auth_client.post("/api/v1/auth/login", json={"email": "traveler@example.com", "password": "wrongpass"})
    assert invalid_login.status_code == 401
    assert invalid_login.json()["error"] == "The email or password is incorrect."


def test_admin_role_persists_is_hashed_and_authorizes_after_login(auth_client):
    from database import User
    from database.connection import SessionLocal

    registered = register(auth_client, "admin@example.com")
    with SessionLocal() as db:
        user = db.get(User, registered["user"]["id"])
        user.is_admin = True
        password_hash = user.password_hash
        db.commit()

    assert password_hash != "password123"
    assert bcrypt.checkpw(b"password123", password_hash.encode())

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["is_admin"] is True
    assert auth_client.get("/api/v1/admin/knowledge/documents", headers=auth_header(login.json())).status_code == 200


def test_auth_validation_and_unexpected_failures_are_not_planner_errors(auth_client):
    invalid = auth_client.post("/api/v1/auth/register", json={"name": "A Traveler", "email": "bad", "password": "short"})
    assert invalid.status_code == 422
    assert "travel plan" not in invalid.json()["error"].lower()

    from api.v1.auth import _auth_service

    def broken_service():
        raise RuntimeError("database unavailable")

    auth_client.app.dependency_overrides[_auth_service] = broken_service
    try:
        failed = auth_client.post("/api/v1/auth/register", json={"name": "A Traveler", "email": "new@example.com", "password": "password123"})
    finally:
        auth_client.app.dependency_overrides.pop(_auth_service, None)
    assert failed.status_code == 500
    assert failed.json()["error"] == "Unable to create your account right now. Please try again."
    assert "travel plan" not in failed.json()["error"].lower()


def test_registration_missing_jwt_configuration_stays_auth_specific(auth_client, monkeypatch):
    monkeypatch.delenv("PACK_GO_JWT_SECRET", raising=False)
    response = auth_client.post(
        "/api/v1/auth/register",
        json={"name": "Configuration Check", "email": "config@example.com", "password": "password123"},
    )

    assert response.status_code == 500
    assert response.json()["error"] == "Unable to create your account right now. Please try again."
    assert "travel plan" not in response.json()["error"].lower()


def test_refresh_rotates_and_rejects_reuse(auth_client):
    result = register(auth_client, "rotate@example.com")
    rotated = auth_client.post("/api/v1/auth/refresh", json={"refresh_token": result["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != result["refresh_token"]
    reused = auth_client.post("/api/v1/auth/refresh", json={"refresh_token": result["refresh_token"]})
    assert reused.status_code == 401
    assert auth_client.post("/api/v1/auth/logout", json={"refresh_token": rotated.json()["refresh_token"]}).status_code == 200
    assert auth_client.post("/api/v1/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}).status_code == 401


def test_trip_ownership_and_preferences(auth_client):
    first = register(auth_client, "first@example.com")
    second = register(auth_client, "second@example.com")
    trip = auth_client.post("/api/v1/trips", headers=auth_header(first), json={"title": "Owned", "destination": "Kyoto", "duration": 2, "total_budget": 500}).json()
    assert auth_client.get(f"/api/v1/trips/{trip['id']}", headers=auth_header(second)).status_code == 404
    assert auth_client.patch(f"/api/v1/trips/{trip['id']}", headers=auth_header(second), json={"title": "Stolen"}).status_code == 404
    assert auth_client.get("/api/v1/users/me/preferences", headers=auth_header(first)).status_code == 200
    updated = auth_client.patch("/api/v1/users/me/preferences", headers=auth_header(first), json={"travel_style": "Luxury", "interests": ["Food"]})
    assert updated.status_code == 200
    assert updated.json()["travel_style"] == "Luxury"
    assert auth_client.get("/api/v1/users/me",).status_code == 401


def test_preferences_empty_defaults_and_full_update_persist(auth_client):
    result = register(auth_client, "preferences@example.com")
    headers = auth_header(result)

    empty = auth_client.get("/api/v1/users/me/preferences", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["interests"] == []
    assert empty.json()["preferred_destinations"] == []

    payload = {
        "travel_style": "Relaxation",
        "interests": ["Beach", "Food"],
        "budget_preference": "Budget",
        "hotel_preference": "Budget",
        "food_preference": "Local",
        "preferred_destinations": ["Goa", "Kyoto"],
    }
    created = auth_client.patch("/api/v1/users/me/preferences", headers=headers, json=payload)
    assert created.status_code == 200
    assert created.json()["preferred_destinations"] == ["Goa", "Kyoto"]

    changed = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"hotel_preference": "Luxury", "interests": ["Culture"]},
    )
    assert changed.status_code == 200
    persisted = auth_client.get("/api/v1/users/me/preferences", headers=headers).json()
    assert persisted["hotel_preference"] == "Luxury"
    assert persisted["interests"] == ["Culture"]
    assert persisted["food_preference"] == "Local"


def test_preferences_accept_frontend_values_and_reject_unknown_values(auth_client):
    result = register(auth_client, "frontend-preferences@example.com")
    headers = auth_header(result)
    payload = {
        "travel_style": "Balanced",
        "budget_preference": "Luxury",
        "hotel_preference": "Boutique",
        "food_preference": "Fine dining",
        "interests": ["Beach"],
        "preferred_destinations": ["Goa"],
    }

    created = auth_client.patch("/api/v1/users/me/preferences", headers=headers, json=payload)
    assert created.status_code == 200
    assert {key: created.json()[key] for key in payload} == payload
    persisted = auth_client.get("/api/v1/users/me/preferences", headers=headers).json()
    assert {key: persisted[key] for key in payload} == payload

    changed = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={
            "travel_style": "Adventure",
            "budget_preference": "Moderate",
            "hotel_preference": "Mid-range",
            "food_preference": "Vegetarian",
            "interests": ["Beach", "Nature"],
            "preferred_destinations": ["Goa", "Kerala"],
        },
    )
    assert changed.status_code == 200
    assert auth_client.get("/api/v1/users/me/preferences", headers=headers).json()["preferred_destinations"] == ["Goa", "Kerala"]

    invalid = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"travel_style": "Unknown", "interests": ["Unknown"]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"] == "Unable to save your preferences. Please check the submitted values."


def test_preferences_require_authentication_and_validate_budget_range(auth_client):
    assert auth_client.get("/api/v1/users/me/preferences").status_code == 401
    assert auth_client.patch("/api/v1/users/me/preferences", json={"travel_style": "Luxury"}).status_code == 401

    result = register(auth_client, "invalid-preferences@example.com")
    invalid = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers=auth_header(result),
        json={"preferred_budget_min": 5000, "preferred_budget_max": 1000},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"] == "Unable to save your preferences. Please check the submitted values."


def test_preference_unexpected_failures_use_preference_error(auth_client):
    from api.v1.users import get_db as preferences_get_db

    def broken_db():
        class BrokenSession:
            def query(self, model):
                raise RuntimeError("database unavailable")

            def close(self):
                pass

        yield BrokenSession()

    result = register(auth_client, "preference-error@example.com")
    auth_client.app.dependency_overrides[preferences_get_db] = broken_db
    try:
        failed = auth_client.get("/api/v1/users/me/preferences", headers=auth_header(result))
    finally:
        auth_client.app.dependency_overrides.pop(preferences_get_db, None)

    assert failed.status_code == 500
    assert failed.json()["error"] == "Unable to save your preferences. Please try again."
    assert "travel plan" not in failed.json()["error"].lower()


def test_preferences_are_isolated_between_users(auth_client):
    first = register(auth_client, "preference-owner@example.com")
    second = register(auth_client, "preference-other@example.com")
    auth_client.patch(
        "/api/v1/users/me/preferences",
        headers=auth_header(first),
        json={"travel_style": "Luxury"},
    )

    other_preferences = auth_client.get("/api/v1/users/me/preferences", headers=auth_header(second)).json()
    assert other_preferences["travel_style"] is None
    assert auth_client.get("/api/v1/users/me/preferences", headers=auth_header(first)).json()["travel_style"] == "Luxury"


def test_email_verification_and_password_reset_are_single_use(auth_client):
    result = register(auth_client, "verify@example.com")
    token = result["verification_token"]
    assert auth_client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert auth_client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400
    forgot = auth_client.post("/api/v1/auth/forgot-password", json={"email": "verify@example.com"})
    assert forgot.status_code == 200
    assert "account exists" in forgot.json()["message"]
    reset = auth_client.post("/api/v1/auth/reset-password", json={"token": forgot.json()["development_token"], "password": "newpassword123"})
    assert reset.status_code == 200
    assert auth_client.post("/api/v1/auth/reset-password", json={"token": forgot.json()["development_token"], "password": "another123"}).status_code == 400
    assert auth_client.post("/api/v1/auth/login", json={"email": "verify@example.com", "password": "newpassword123"}).status_code == 200
