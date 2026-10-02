import importlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def journal_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'journal.db').as_posix()}")
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
        result = client.post("/api/v1/auth/register", json={
            "name": name,
            "email": email,
            "password": "password123",
        }).json()
        client.headers.update({"Authorization": f"Bearer {result['access_token']}"})
        return client, result["user"]

    return (
        register("Owner", "owner@example.com"),
        register("Member", "member@example.com"),
        register("Outsider", "outsider@example.com"),
    )


def _trip(client, title="Journal trip"):
    return client.post("/api/v1/trips", json={
        "title": title,
        "destination": "Kyoto",
        "duration": 5,
        "total_budget": 1200,
        "budget_currency": "JPY",
        "itinerary": [],
    }).json()


def test_personal_journal_crud_timeline_media_and_statistics(journal_clients):
    (owner, owner_user), _, _ = journal_clients
    trip = _trip(owner)
    endpoint = f"/api/v1/trips/{trip['id']}/journal"
    later = owner.post(endpoint, json={
        "title": "Evening walk",
        "content": "Lanterns along the river.",
        "occurred_at": "2026-04-12T19:30:00Z",
        "media_references": ["https://example.com/river.jpg"],
    })
    assert later.status_code == 201, later.text
    assert later.json()["title"] == "Evening walk"
    assert later.json()["author_name"] == "Owner"
    assert later.json()["occurred_at"].startswith("2026-04-12T19:30:00")
    assert later.json()["created_at"]
    first = owner.post(endpoint, json={
        "content": "Arrived in Kyoto.",
        "occurred_at": "2026-04-10T09:00:00Z",
    })
    assert first.status_code == 201, first.text
    assert first.json()["created_by_user_id"] == owner_user["id"]

    timeline = owner.get(endpoint)
    assert timeline.status_code == 200
    assert [entry["content"] for entry in timeline.json()] == ["Arrived in Kyoto.", "Lanterns along the river."]
    assert timeline.json()[1]["title"] == "Evening walk"
    assert timeline.json()[1]["author_name"] == "Owner"
    assert timeline.json()[1]["media_references"] == ["https://example.com/river.jpg"]

    invalid_media = owner.post(endpoint, json={"content": "Bad reference", "media_references": ["javascript:alert(1)"]})
    assert invalid_media.status_code == 422
    invalid_update = owner.patch(f"/api/v1/journal-entries/{first.json()['id']}", json={"content": None})
    assert invalid_update.status_code == 422

    expense = owner.post(f"/api/v1/trips/{trip['id']}/expenses", json={
        "amount": "42.50",
        "category": "food",
        "participants": [{"user_id": owner_user["id"]}],
    })
    assert expense.status_code == 201, expense.text

    statistics = owner.get(f"{endpoint}/statistics")
    assert statistics.status_code == 200
    assert statistics.json() == {
        "trip_id": trip["id"],
        "planned_duration_days": 5,
        "journal_entry_count": 2,
        "journal_days_covered": 2,
        "media_reference_count": 1,
        "expense_total": "42.50",
        "expense_currency": "JPY",
    }

    update = owner.patch(f"/api/v1/journal-entries/{later.json()['id']}", json={
        "title": "Riverside evening",
        "content": "Updated note.",
        "media_references": [],
    })
    assert update.status_code == 200, update.text
    assert update.json()["title"] == "Riverside evening"
    assert update.json()["content"] == "Updated note."
    assert update.json()["media_references"] == []
    assert owner.delete(f"/api/v1/journal-entries/{first.json()['id']}").status_code == 204
    assert len(owner.get(endpoint).json()) == 1


def test_group_journal_access_author_mutations_and_removed_member(journal_clients):
    (owner, _), (member, member_user), (outsider, _) = journal_clients
    trip = _trip(owner, "Shared journal")
    trip_id = trip["id"]
    assert owner.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    invitation = owner.post(f"/api/v1/trips/{trip_id}/invitations", json={"invitee_user_id": member_user["id"]}).json()
    assert member.post(f"/api/v1/invitations/{invitation['token']}/accept").status_code == 200

    endpoint = f"/api/v1/trips/{trip_id}/journal"
    entry = member.post(endpoint, json={"title": "Shared memory", "content": "A shared trip moment."})
    assert entry.status_code == 201, entry.text
    assert len(owner.get(endpoint).json()) == 1
    entry_id = entry.json()["id"]
    assert owner.patch(f"/api/v1/journal-entries/{entry_id}", json={"content": "Owner edit"}).status_code == 403
    assert owner.delete(f"/api/v1/journal-entries/{entry_id}").status_code == 403
    assert outsider.get(endpoint).status_code == 404
    assert outsider.patch(f"/api/v1/journal-entries/{entry_id}", json={"content": "No access"}).status_code == 404
    assert outsider.get(f"{endpoint}/statistics").status_code == 404

    assert owner.delete(f"/api/v1/trips/{trip_id}/members/{member_user['id']}").status_code == 204
    assert member.get(endpoint).status_code == 404
    assert member.get(f"{endpoint}/statistics").status_code == 404
    assert member.patch(f"/api/v1/journal-entries/{entry_id}", json={"content": "No longer a member"}).status_code == 404