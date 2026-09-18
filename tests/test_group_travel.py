import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def group_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'group.db').as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")
    import database.connection as connection
    import database as database_module
    connection = importlib.reload(connection)
    importlib.reload(database_module)
    from database.base import Base
    Base.metadata.create_all(bind=connection.engine)
    import main
    main = importlib.reload(main)
    client = TestClient(main.app)
    auth = client.post("/api/v1/auth/register", json={"name": "Owner", "email": "owner@example.com", "password": "password123"}).json()
    client.headers.update({"Authorization": f"Bearer {auth['access_token']}"})
    return client


def test_group_workspace_proposal_vote_checklist_and_chat(group_client):
    trip = group_client.post("/api/v1/trips", json={"title": "Shared", "destination": "Kyoto", "duration": 3, "total_budget": 1000, "itinerary": []}).json()
    trip_id = trip["id"]
    converted = group_client.post(f"/api/v1/trips/{trip_id}/group")
    assert converted.status_code == 200
    assert group_client.post(f"/api/v1/trips/{trip_id}/group").json()["member_count"] == 1
    assert len(group_client.get(f"/api/v1/trips/{trip_id}/members").json()["members"]) == 1

    proposal = group_client.post(f"/api/v1/trips/{trip_id}/proposals", json={"proposal_type": "other", "title": "Dinner", "payload": {"choice": "ramen"}})
    assert proposal.status_code == 201
    proposal_id = proposal.json()["id"]
    assert group_client.put(f"/api/v1/proposals/{proposal_id}/vote", json={"choice_key": "approve"}).status_code == 200
    decision = group_client.post(f"/api/v1/proposals/{proposal_id}/finalize")
    assert decision.status_code == 200
    assert group_client.post(f"/api/v1/proposals/{proposal_id}/finalize").status_code == 409

    item = group_client.post(f"/api/v1/trips/{trip_id}/checklist", json={"title": "Book tickets"})
    assert item.status_code == 201
    assert group_client.patch(f"/api/v1/checklist-items/{item.json()['id']}", json={"completed": True}).json()["completed"] is True
    message = group_client.post(f"/api/v1/trips/{trip_id}/messages", json={"body": "Ready to go"})
    assert message.status_code == 201
    assert len(group_client.get(f"/api/v1/trips/{trip_id}/messages").json()["messages"]) == 1


def test_existing_user_invitation_is_visible_and_accepted(group_client):
    trip = group_client.post("/api/v1/trips", json={"title": "Shared", "destination": "Goa", "duration": 3, "total_budget": 1000, "itinerary": []}).json()
    trip_id = trip["id"]
    assert group_client.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    invitee = group_client.post("/api/v1/auth/register", json={"name": "Invitee", "email": "invitee@example.com", "password": "password123"}).json()
    invitation = group_client.post(f"/api/v1/trips/{trip_id}/invitations", json={"invitee_email": "invitee@example.com"})
    assert invitation.status_code == 201
    assert invitation.json()["invitee_user_id"] == invitee["user"]["id"]
    assert invitation.json()["invitee_email"] is None
    assert invitation.json()["status"] == "pending"
    invitee_client = TestClient(group_client.app)
    invitee_client.headers.update({"Authorization": f"Bearer {invitee['access_token']}"})
    notifications = invitee_client.get("/api/v1/notifications").json()["notifications"]
    assert any(item["event_type"] == "invitation_created" and item["trip_id"] == trip_id for item in notifications)
    accepted = invitee_client.post(f"/api/v1/invitations/{invitation.json()['token']}/accept")
    assert accepted.status_code == 200
    assert any(member["user_id"] == invitee["user"]["id"] for member in group_client.get(f"/api/v1/trips/{trip_id}/members").json()["members"])


def test_link_invitation_preview_hash_storage_and_duplicate_acceptance(group_client):
    from database.connection import SessionLocal
    from database.models import TripInvitation
    from services.collaboration_service import token_digest

    trip = group_client.post("/api/v1/trips", json={"title": "Link trip", "destination": "Lisbon", "duration": 4, "total_budget": 1200, "itinerary": []}).json()
    trip_id = trip["id"]
    assert group_client.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    invitation = group_client.post(f"/api/v1/trips/{trip_id}/invitations", json={"expires_in_days": 2})
    assert invitation.status_code == 201
    body = invitation.json()
    assert body["token"]
    assert body["invitee_user_id"] is None
    assert body["invitee_email"] is None

    with SessionLocal() as db:
        stored = db.get(TripInvitation, body["id"])
        assert stored.token_hash == token_digest(body["token"])
        assert stored.token_hash != body["token"]

    preview = group_client.get(f"/api/v1/invitations/{body['token']}")
    assert preview.status_code == 200
    assert preview.json()["trip_title"] == "Link trip"

    invitee = group_client.post("/api/v1/auth/register", json={"name": "Link invitee", "email": "link@example.com", "password": "password123"}).json()
    invitee_client = TestClient(group_client.app)
    invitee_client.headers.update({"Authorization": f"Bearer {invitee['access_token']}"})
    assert invitee_client.post(f"/api/v1/invitations/{body['token']}/accept").status_code == 200
    assert invitee_client.post(f"/api/v1/invitations/{body['token']}/accept").status_code == 403
