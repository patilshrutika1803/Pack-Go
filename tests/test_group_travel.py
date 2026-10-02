import importlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
    assert message.json()["sender_name"] == "Owner"
    listed_messages = group_client.get(f"/api/v1/trips/{trip_id}/messages").json()["messages"]
    assert len(listed_messages) == 1
    assert listed_messages[0]["sender_name"] == "Owner"


def test_proposal_vote_updates_persisted_results(group_client):
    trip = group_client.post("/api/v1/trips", json={"title": "Shared", "destination": "Kyoto", "duration": 3, "total_budget": 1000, "itinerary": []}).json()
    trip_id = trip["id"]
    assert group_client.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    proposal = group_client.post(f"/api/v1/trips/{trip_id}/proposals", json={"proposal_type": "other", "title": "Dinner", "payload": {"choice": "ramen"}})
    assert proposal.status_code == 201
    proposal_id = proposal.json()["id"]

    vote = group_client.put(f"/api/v1/proposals/{proposal_id}/vote", json={"choice_key": "Support"})
    assert vote.status_code == 200
    results = group_client.get(f"/api/v1/proposals/{proposal_id}/results")
    assert results.status_code == 200
    assert results.json()["counts"] == {"Support": 1}
    assert results.json()["user_vote"] == "Support"

    updated_vote = group_client.put(f"/api/v1/proposals/{proposal_id}/vote", json={"choice_key": "Oppose"})
    assert updated_vote.status_code == 200
    results = group_client.get(f"/api/v1/proposals/{proposal_id}/results")
    assert results.json()["counts"] == {"Oppose": 1}
    assert results.json()["user_vote"] == "Oppose"


def test_group_trip_api_preserves_saved_itinerary(group_client):
    itinerary = [
        {"day_number": 1, "activities": ["Walk", "Museum"]},
        {"day_number": 2, "activities": ["Market"]},
    ]
    trip = group_client.post("/api/v1/trips", json={
        "title": "Shared itinerary",
        "destination": "Kyoto",
        "duration": 2,
        "total_budget": 1000,
        "itinerary": itinerary,
    }).json()
    assert group_client.post(f"/api/v1/trips/{trip['id']}/group").status_code == 200

    saved_trip = group_client.get(f"/api/v1/trips/{trip['id']}")

    assert saved_trip.status_code == 200
    assert saved_trip.json()["itinerary"] == itinerary


def test_personal_trip_requires_conversion_before_group_access(group_client):
    from database.connection import SessionLocal
    from database.models import Trip, TripMember

    trip = group_client.post("/api/v1/trips", json={"title": "Personal", "destination": "Goa", "duration": 2, "total_budget": 500, "itinerary": []}).json()
    trip_id = trip["id"]
    with SessionLocal() as db:
        stored_trip = db.get(Trip, trip_id)
        db.add(TripMember(id=str(uuid4()), trip_id=trip_id, user_id=stored_trip.user_id, role="owner", status="active"))
        db.commit()

    assert group_client.get(f"/api/v1/trips/{trip_id}/workspace").status_code == 404
    assert group_client.post(f"/api/v1/trips/{trip_id}/checklist", json={"title": "Group task"}).status_code == 404
    converted = group_client.post(f"/api/v1/trips/{trip_id}/group")
    assert converted.status_code == 200
    assert converted.json()["is_group"] is True
    assert group_client.get(f"/api/v1/trips/{trip_id}/workspace").json()["is_group"] is True


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

    public_client = TestClient(group_client.app)
    preview = public_client.get(f"/api/v1/invitations/{body['token']}")
    assert preview.status_code == 200
    assert preview.json()["trip_title"] == "Link trip"
    assert public_client.post(f"/api/v1/invitations/{body['token']}/accept").status_code == 401
    assert public_client.get("/api/v1/invitations/invalid-token").status_code == 403

    invitee = group_client.post("/api/v1/auth/register", json={"name": "Link invitee", "email": "link@example.com", "password": "password123"}).json()
    invitee_client = TestClient(group_client.app)
    invitee_client.headers.update({"Authorization": f"Bearer {invitee['access_token']}"})
    assert invitee_client.post(f"/api/v1/invitations/{body['token']}/accept").status_code == 200
    assert invitee_client.post(f"/api/v1/invitations/{body['token']}/accept").status_code == 403
    assert public_client.get(f"/api/v1/invitations/{body['token']}").json()["status"] == "accepted"

    expired = group_client.post(f"/api/v1/trips/{trip_id}/invitations", json={"expires_in_days": 2}).json()
    with SessionLocal() as db:
        stored = db.get(TripInvitation, expired["id"])
        stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    expired_preview = public_client.get(f"/api/v1/invitations/{expired['token']}")
    assert expired_preview.status_code == 200
    assert expired_preview.json()["status"] == "expired"
    assert invitee_client.post(f"/api/v1/invitations/{expired['token']}/accept").status_code == 403
