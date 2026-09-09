import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "api_v1_trips.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    import database.connection as connection_module
    import database as database_module

    connection_module = importlib.reload(connection_module)
    database_module = importlib.reload(database_module)

    from database.base import Base

    Base.metadata.create_all(bind=connection_module.engine)

    import main as main_module

    main_module = importlib.reload(main_module)

    return TestClient(main_module.app)


def build_trip_payload(**overrides):
    payload = {
        "title": "Kyoto City Break",
        "destination": "Kyoto, Japan",
        "duration": 7,
        "total_budget": 1800.0,
        "budget_currency": "INR",
        "group_size": 2,
        "travel_style": "balanced",
        "travel_dates": "2026-04-10 to 2026-04-17",
        "interests": ["temples", "food", "culture"],
        "things_to_avoid": ["crowded areas"],
        "itinerary": [{"day_number": 1, "theme": "Arrival"}],
        "weather": {"summary": "Mild spring weather"},
        "budget_breakdown": {"total_estimated": 1750.0, "currency": "INR"},
        "critic_review": {"overall_score": 8.5},
        "revision_history": [{"iteration": 1, "score": 8.5, "changes_made": "Initial draft"}],
        "data_freshness": {"weather": "live", "budget": "live"},
        "original_query": "Plan a cultural trip to Kyoto",
    }
    payload.update(overrides)
    return payload


def test_post_api_v1_trips_creates_trip(api_client):
    response = api_client.post("/api/v1/trips", json=build_trip_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"]
    assert payload["destination"] == "Kyoto, Japan"
    assert payload["title"] == "Kyoto City Break"
    assert payload["budget_currency"] == "INR"


def test_get_api_v1_trips_returns_newest_first(api_client):
    first_response = api_client.post("/api/v1/trips", json=build_trip_payload(title="First Trip"))
    second_response = api_client.post("/api/v1/trips", json=build_trip_payload(title="Second Trip"))

    list_response = api_client.get("/api/v1/trips")

    assert list_response.status_code == 200
    trips = list_response.json()
    assert [trip["id"] for trip in trips] == [second_response.json()["id"], first_response.json()["id"]]
    assert trips[0]["title"] == "Second Trip"


def test_get_api_v1_trips_single_returns_trip_or_404(api_client):
    created = api_client.post("/api/v1/trips", json=build_trip_payload())
    trip_id = created.json()["id"]

    single_response = api_client.get(f"/api/v1/trips/{trip_id}")
    missing_response = api_client.get("/api/v1/trips/not-found")

    assert single_response.status_code == 200
    assert single_response.json()["id"] == trip_id
    assert missing_response.status_code == 404
    assert missing_response.json()["error"] == "Trip not found."


def test_patch_api_v1_trips_updates_selected_fields(api_client):
    created = api_client.post("/api/v1/trips", json=build_trip_payload())
    trip_id = created.json()["id"]

    patch_response = api_client.patch(
        f"/api/v1/trips/{trip_id}",
        json={"travel_style": "luxury", "total_budget": 2200.0},
    )
    missing_response = api_client.patch("/api/v1/trips/not-found", json={"travel_style": "luxury"})

    assert patch_response.status_code == 200
    payload = patch_response.json()
    assert payload["travel_style"] == "luxury"
    assert payload["total_budget"] == 2200.0
    assert payload["destination"] == "Kyoto, Japan"
    assert missing_response.status_code == 404
    assert missing_response.json()["error"] == "Trip not found."


def test_delete_api_v1_trips_removes_trip(api_client):
    created = api_client.post("/api/v1/trips", json=build_trip_payload())
    trip_id = created.json()["id"]

    delete_response = api_client.delete(f"/api/v1/trips/{trip_id}")
    after_delete = api_client.get(f"/api/v1/trips/{trip_id}")
    missing_delete = api_client.delete("/api/v1/trips/not-found")

    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Trip deleted successfully."
    assert after_delete.status_code == 404
    assert missing_delete.status_code == 404
    assert missing_delete.json()["error"] == "Trip not found."


def test_post_api_v1_trips_rejects_missing_required_fields(api_client):
    response = api_client.post("/api/v1/trips", json={"destination": "Kyoto, Japan"})

    assert response.status_code == 422
