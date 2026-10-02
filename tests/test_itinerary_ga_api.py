import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ga_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'itinerary_ga.db').as_posix()}")
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

    owner, _ = register("GA Owner", "ga-owner@example.com")
    member, member_user = register("GA Member", "ga-member@example.com")
    outsider, _ = register("GA Outsider", "ga-outsider@example.com")
    return owner, member, member_user, outsider


def _itinerary():
    return [{
        "day_number": 1,
        "activities": ["Walk"],
        "attractions": [
            {"place": {"name": "Museum", "entry_fee": "₹100"}, "timing": "10:00 AM - 12:00 PM"},
            {"place": {"name": "Gallery"}, "timing": "11:00 AM - 1:00 PM"},
        ],
    }]


def _create_trip(client, itinerary=None):
    return client.post("/api/v1/trips", json={
        "title": "GA Test Trip",
        "destination": "Kyoto",
        "duration": 2,
        "total_budget": 500,
        "interests": ["museums"],
        "things_to_avoid": ["crowds"],
        "itinerary": _itinerary() if itinerary is None else itinerary,
    }).json()


def test_ga_endpoint_returns_preview_and_does_not_overwrite_saved_itinerary(ga_clients):
    owner, _, _, _ = ga_clients
    trip = _create_trip(owner)

    response = owner.post(f"/api/v1/trips/{trip['id']}/itinerary/ga-optimize", json={"random_seed": 42})
    saved_after = owner.get(f"/api/v1/trips/{trip['id']}").json()["itinerary"]

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimized"
    assert body["algorithm"] == "Genetic Algorithm"
    assert body["final_fitness"] > body["baseline_fitness"]
    assert body["generations_executed"] == 20
    assert body["optimized_itinerary"] != saved_after
    assert saved_after == _itinerary()
    assert body["unavailable_constraints"]


def test_ga_endpoint_reports_insufficient_and_malformed_itineraries(ga_clients):
    owner, _, _, _ = ga_clients
    empty_trip = _create_trip(owner, [])
    malformed_trip = _create_trip(owner, [{"day_number": 1, "activities": [5]}])

    empty = owner.post(f"/api/v1/trips/{empty_trip['id']}/itinerary/ga-optimize", json={})
    malformed = owner.post(f"/api/v1/trips/{malformed_trip['id']}/itinerary/ga-optimize", json={})

    assert empty.status_code == malformed.status_code == 200
    assert empty.json()["status"] == "insufficient_data"
    assert malformed.json()["status"] == "insufficient_data"


def test_ga_endpoint_enforces_configuration_bounds_and_trip_existence(ga_clients):
    owner, _, _, _ = ga_clients

    excessive = owner.post("/api/v1/trips/not-a-trip/itinerary/ga-optimize", json={"generations": 101})
    missing = owner.post("/api/v1/trips/not-a-trip/itinerary/ga-optimize", json={})

    assert excessive.status_code == 422
    assert missing.status_code == 404


def test_ga_endpoint_requires_authentication_and_protects_trip_access(ga_clients):
    owner, member, member_user, outsider = ga_clients
    private_trip = _create_trip(owner)
    assert outsider.post(f"/api/v1/trips/{private_trip['id']}/itinerary/ga-optimize", json={}).status_code == 404

    group_trip = _create_trip(ga_clients[0])
    trip_id = group_trip["id"]
    assert ga_clients[0].post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    invitation = ga_clients[0].post(
        f"/api/v1/trips/{trip_id}/invitations",
        json={"invitee_user_id": member_user["user"]["id"]},
    )
    assert invitation.status_code == 201
    assert member.post(f"/api/v1/invitations/{invitation.json()['token']}/accept").status_code == 200
    assert member.post(f"/api/v1/trips/{trip_id}/itinerary/ga-optimize", json={}).status_code == 200
    assert outsider.post(f"/api/v1/trips/{trip_id}/itinerary/ga-optimize", json={}).status_code == 404

    owner.headers.clear()
    assert owner.post(f"/api/v1/trips/{private_trip['id']}/itinerary/ga-optimize", json={}).status_code == 401