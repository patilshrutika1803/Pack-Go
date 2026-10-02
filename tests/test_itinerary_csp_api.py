import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def csp_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'itinerary_csp.db').as_posix()}")
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
        return client, result

    owner, owner_user = register("CSP Owner", "csp-owner@example.com")
    member, member_user = register("CSP Member", "csp-member@example.com")
    outsider, _ = register("CSP Outsider", "csp-outsider@example.com")
    return owner, owner_user, member, member_user, outsider


def _trip_payload(itinerary):
    return {
        "title": "CSP Test Trip",
        "destination": "Kyoto",
        "duration": 2,
        "total_budget": 500,
        "itinerary": itinerary,
    }


def _valid_itinerary():
    return [{
        "day_number": 1,
        "activities": ["Walk around town"],
        "attractions": [
            {"place": {"name": "Museum"}, "timing": "10:00 AM - 12:00 PM"},
            {"place": {"name": "Gallery"}, "timing": "11:00 AM - 1:00 PM"},
        ],
    }]


def test_csp_endpoint_returns_a_deterministic_valid_schedule(csp_clients):
    owner, _, _, _, _ = csp_clients
    trip = owner.post("/api/v1/trips", json=_trip_payload(_valid_itinerary())).json()

    first = owner.post(f"/api/v1/trips/{trip['id']}/itinerary/csp-optimize", json={})
    second = owner.post(f"/api/v1/trips/{trip['id']}/itinerary/csp-optimize", json={})

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["valid"] is True
    assert [(item["name"], item["day_number"]) for item in first.json()["assignments"]] == [
        ("Walk around town", 1), ("Museum", 1), ("Gallery", 2),
    ]


def test_csp_endpoint_handles_insufficient_and_malformed_saved_itineraries(csp_clients):
    owner, _, _, _, _ = csp_clients
    empty_trip = owner.post("/api/v1/trips", json=_trip_payload([])).json()
    malformed_trip = owner.post("/api/v1/trips", json=_trip_payload([{"day_number": 1, "activities": [5]}])).json()

    empty = owner.post(f"/api/v1/trips/{empty_trip['id']}/itinerary/csp-optimize", json={})
    malformed = owner.post(f"/api/v1/trips/{malformed_trip['id']}/itinerary/csp-optimize", json={})

    assert empty.status_code == 200
    assert empty.json()["status"] == "insufficient_data"
    assert malformed.status_code == 200
    assert malformed.json()["status"] == "insufficient_data"


def test_csp_endpoint_rejects_malformed_request_and_invalid_trip(csp_clients):
    owner, _, _, _, _ = csp_clients

    malformed = owner.post("/api/v1/trips/missing/itinerary/csp-optimize", json={"unexpected": True})
    missing = owner.post("/api/v1/trips/missing/itinerary/csp-optimize", json={})

    assert malformed.status_code == 422
    assert missing.status_code == 404


def test_csp_endpoint_protects_private_trip_and_allows_active_group_member(csp_clients):
    owner, _, member, member_user, outsider = csp_clients
    private_trip = owner.post("/api/v1/trips", json=_trip_payload(_valid_itinerary())).json()

    assert outsider.post(f"/api/v1/trips/{private_trip['id']}/itinerary/csp-optimize", json={}).status_code == 404

    group_trip = owner.post("/api/v1/trips", json=_trip_payload(_valid_itinerary())).json()
    trip_id = group_trip["id"]
    assert owner.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    invitation = owner.post(
        f"/api/v1/trips/{trip_id}/invitations",
        json={"invitee_user_id": member_user["user"]["id"]},
    )
    assert invitation.status_code == 201
    assert member.post(f"/api/v1/invitations/{invitation.json()['token']}/accept").status_code == 200
    assert member.post(f"/api/v1/trips/{trip_id}/itinerary/csp-optimize", json={}).status_code == 200
    assert outsider.post(f"/api/v1/trips/{trip_id}/itinerary/csp-optimize", json={}).status_code == 404


def test_csp_endpoint_requires_authentication(csp_clients):
    owner, _, _, _, _ = csp_clients
    trip = owner.post("/api/v1/trips", json=_trip_payload(_valid_itinerary())).json()
    owner.headers.clear()

    response = owner.post(f"/api/v1/trips/{trip['id']}/itinerary/csp-optimize", json={})

    assert response.status_code == 401