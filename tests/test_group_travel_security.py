import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def security_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'security.db').as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")
    import database.connection as connection
    import database as database_module
    importlib.reload(connection)
    importlib.reload(database_module)
    from database.base import Base
    Base.metadata.create_all(bind=connection.engine)
    import main
    main = importlib.reload(main)

    def register(name, email):
        client = TestClient(main.app)
        result = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "password123"}).json()
        client.headers.update({"Authorization": f"Bearer {result['access_token']}"})
        return client, result["user"]

    owner, owner_user = register("Owner", "owner@example.com")
    member, member_user = register("Member", "member@example.com")
    outsider, outsider_user = register("Outsider", "outsider@example.com")
    return owner, owner_user, member, member_user, outsider, outsider_user


def test_non_member_cross_trip_and_removed_member_are_denied(security_clients):
    owner, _, member, member_user, outsider, _ = security_clients
    trip = owner.post("/api/v1/trips", json={"title": "Private", "destination": "Goa", "duration": 2, "total_budget": 500, "itinerary": []}).json()
    trip_id = trip["id"]
    assert owner.post(f"/api/v1/trips/{trip_id}/group").status_code == 200

    assert outsider.get(f"/api/v1/trips/{trip_id}").status_code == 404
    assert outsider.get(f"/api/v1/trips/{trip_id}/members").status_code == 404
    invitation = owner.post(f"/api/v1/trips/{trip_id}/invitations", json={"invitee_user_id": member_user["id"]}).json()
    assert member.post(f"/api/v1/invitations/{invitation['token']}/accept").status_code == 200
    assert owner.delete(f"/api/v1/trips/{trip_id}/members/{member_user['id']}").status_code == 204
    assert member.get(f"/api/v1/trips/{trip_id}").status_code == 404
    assert member.get(f"/api/v1/trips/{trip_id}/proposals").status_code == 404


def test_global_admin_is_not_trip_admin_and_client_actor_fields_are_ignored(security_clients):
    owner, _, _, _, outsider, outsider_user = security_clients
    from database.connection import SessionLocal
    from database.models import User
    with SessionLocal() as db:
        db.get(User, outsider_user["id"]).is_admin = True
        db.commit()

    trip = owner.post("/api/v1/trips", json={"title": "Private", "destination": "Kyoto", "duration": 2, "total_budget": 500, "itinerary": []}).json()
    trip_id = trip["id"]
    assert owner.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    assert outsider.get(f"/api/v1/trips/{trip_id}").status_code == 404
    assert outsider.patch(f"/api/v1/trips/{trip_id}", json={"title": "forged", "user_id": outsider_user["id"], "role": "owner"}).status_code == 422


def test_owner_cannot_leave_or_be_removed_and_transfer_requires_active_member(security_clients):
    owner, _, _, _, outsider, outsider_user = security_clients
    trip = owner.post("/api/v1/trips", json={"title": "Private", "destination": "Delhi", "duration": 2, "total_budget": 500, "itinerary": []}).json()
    trip_id = trip["id"]
    assert owner.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    assert owner.post(f"/api/v1/trips/{trip_id}/leave").status_code == 403
    assert owner.delete(f"/api/v1/trips/{trip_id}/members/{outsider_user['id']}").status_code == 404
    assert owner.post(f"/api/v1/trips/{trip_id}/ownership", json={"target_user_id": outsider_user["id"]}).status_code in {403, 404}
