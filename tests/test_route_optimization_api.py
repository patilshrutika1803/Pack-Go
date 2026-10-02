import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "route_optimization.db"
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
    client = TestClient(main_module.app)
    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Route Owner", "email": "route-owner@example.com", "password": "password123"},
    ).json()
    client.headers.update({"Authorization": f"Bearer {registered['access_token']}"})
    return client


def trip_payload(itinerary=None):
    return {
        "title": "Coordinate Route",
        "destination": "Mumbai",
        "duration": 1,
        "total_budget": 1000,
        "itinerary": itinerary or [
            {
                "day_number": 1,
                "attractions": [
                    {"place": {"name": "Gateway", "latitude": 18.9220, "longitude": 72.8347}},
                    {"place": {"name": "Marine Drive", "latitude": 18.9440, "longitude": 72.8230}},
                    {"place": {"name": "Colaba", "latitude": 18.9067, "longitude": 72.8147}},
                ],
            }
        ],
    }


def test_route_endpoint_uses_saved_coordinates_and_returns_a_star_path(api_client):
    trip = api_client.post("/api/v1/trips", json=trip_payload()).json()

    locations_response = api_client.get(f"/api/v1/trips/{trip['id']}/route/locations")
    assert locations_response.status_code == 200
    locations = locations_response.json()["locations"]
    assert [location["id"] for location in locations] == [
        "day-1-attraction-1",
        "day-1-attraction-2",
        "day-1-attraction-3",
    ]

    response = api_client.post(
        f"/api/v1/trips/{trip['id']}/route/optimize",
        json={"start_location_id": locations[0]["id"], "goal_location_id": locations[2]["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["algorithm"] == "A*"
    assert body["status"] == "optimized"
    assert body["route"]["ordered_locations"][0]["name"] == "Gateway"
    assert body["route"]["ordered_locations"][-1]["name"] == "Colaba"
    assert body["route"]["total_distance_km"] > 0
    assert body["route"]["search_stats"]["expanded_count"] >= 1


def test_route_endpoint_reports_insufficient_locations_and_rejects_malformed_data(api_client):
    no_coordinates = api_client.post(
        "/api/v1/trips",
        json=trip_payload([{"day_number": 1, "attractions": [{"place": {"name": "No coordinates"}}]}]),
    ).json()
    response = api_client.get(f"/api/v1/trips/{no_coordinates['id']}/route/locations")
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_locations"
    assert response.json()["locations"] == []

    malformed = api_client.post(
        "/api/v1/trips",
        json=trip_payload([{"day_number": 1, "attractions": [{"place": {"name": "Bad point", "latitude": 100, "longitude": 2}}]}]),
    ).json()
    assert api_client.get(f"/api/v1/trips/{malformed['id']}/route/locations").status_code == 422


def test_route_endpoint_validates_selection_and_trip_access(api_client):
    trip = api_client.post("/api/v1/trips", json=trip_payload()).json()
    trip_id = trip["id"]
    assert api_client.post(f"/api/v1/trips/{trip_id}/route/optimize", json={"start_location_id": "only-one"}).status_code == 422
    assert api_client.post(
        f"/api/v1/trips/{trip_id}/route/optimize",
        json={"start_location_id": "missing", "goal_location_id": "also-missing"},
    ).status_code == 422
    assert api_client.get("/api/v1/trips/not-a-trip/route/locations").status_code == 404

    stranger = TestClient(api_client.app)
    registered = stranger.post(
        "/api/v1/auth/register",
        json={"name": "Route Stranger", "email": "route-stranger@example.com", "password": "password123"},
    ).json()
    stranger.headers.update({"Authorization": f"Bearer {registered['access_token']}"})
    assert stranger.get(f"/api/v1/trips/{trip_id}/route/locations").status_code == 404
    stranger.headers.clear()
    assert stranger.get(f"/api/v1/trips/{trip_id}/route/locations").status_code == 401


def test_group_member_can_optimize_route_but_nonmember_cannot(api_client):
    trip = api_client.post("/api/v1/trips", json=trip_payload()).json()
    trip_id = trip["id"]
    assert api_client.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    member_data = api_client.post(
        "/api/v1/auth/register",
        json={"name": "Route Member", "email": "route-member@example.com", "password": "password123"},
    ).json()
    invitation = api_client.post(
        f"/api/v1/trips/{trip_id}/invitations", json={"invitee_email": "route-member@example.com"}
    ).json()
    member = TestClient(api_client.app)
    member.headers.update({"Authorization": f"Bearer {member_data['access_token']}"})
    assert member.post(f"/api/v1/invitations/{invitation['token']}/accept").status_code == 200
    assert member.get(f"/api/v1/trips/{trip_id}/route/locations").status_code == 200

    outsider = TestClient(api_client.app)
    outsider_data = outsider.post(
        "/api/v1/auth/register",
        json={"name": "Route Outsider", "email": "route-outsider@example.com", "password": "password123"},
    ).json()
    outsider.headers.update({"Authorization": f"Bearer {outsider_data['access_token']}"})
    assert outsider.get(f"/api/v1/trips/{trip_id}/route/locations").status_code == 404