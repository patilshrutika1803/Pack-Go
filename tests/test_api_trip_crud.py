import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "api_v1_trips.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")

    import database.connection as connection_module
    import database as database_module

    connection_module = importlib.reload(connection_module)
    database_module = importlib.reload(database_module)

    from database.base import Base

    Base.metadata.create_all(bind=connection_module.engine)

    import main as main_module

    main_module = importlib.reload(main_module)

    client = TestClient(main_module.app)
    registration = client.post(
        "/api/v1/auth/register",
        json={"name": "Trip Tester", "email": "trip-tester@example.com", "password": "password123"},
    )
    client.headers.update({"Authorization": f"Bearer {registration.json()['access_token']}"})
    return client


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


def test_trip_access_is_owner_scoped_and_unauthenticated_access_is_rejected(api_client):
    created = api_client.post("/api/v1/trips", json=build_trip_payload()).json()
    trip_id = created["id"]
    owner_headers = dict(api_client.headers)
    second_registration = api_client.post(
        "/api/v1/auth/register",
        json={"name": "Second Traveler", "email": "second-trip@example.com", "password": "password123"},
    ).json()
    api_client.headers.update({"Authorization": f"Bearer {second_registration['access_token']}"})

    assert api_client.get("/api/v1/trips").json() == []
    assert api_client.get(f"/api/v1/trips/{trip_id}").status_code == 404
    assert api_client.patch(f"/api/v1/trips/{trip_id}", json={"title": "Stolen"}).status_code == 404
    assert api_client.delete(f"/api/v1/trips/{trip_id}").status_code == 404

    api_client.headers.clear()
    assert api_client.get("/api/v1/trips").status_code == 401
    api_client.headers.update(owner_headers)
    assert api_client.get(f"/api/v1/trips/{trip_id}").status_code == 200


def test_trip_creation_requires_authentication(api_client):
    api_client.headers.clear()
    assert api_client.post("/api/v1/trips", json=build_trip_payload()).status_code == 401


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


def test_patch_api_v1_trips_regenerate_day_updates_requested_day(api_client, monkeypatch):
    created = api_client.post(
        "/api/v1/trips",
        json=build_trip_payload(
            itinerary=[
                {
                    "day_number": 1,
                    "theme": "Arrival",
                    "hotel": {"name": "Hotel A", "stars": 3, "price_per_night": 100, "amenities": ["Wi-Fi"], "description": "Hotel A description."},
                    "meals": [],
                    "attractions": [],
                    "activities": ["Check-in"],
                    "transport": {"mode": "Taxi", "estimated_cost": 200},
                    "estimated_day_cost": 1000,
                },
                {
                    "day_number": 2,
                    "theme": "Culture",
                    "hotel": {"name": "Hotel B", "stars": 4, "price_per_night": 150, "amenities": ["Wi-Fi"], "description": "Hotel B description."},
                    "meals": [],
                    "attractions": [],
                    "activities": ["Museum"],
                    "transport": {"mode": "Taxi", "estimated_cost": 200},
                    "estimated_day_cost": 1500,
                },
                {
                    "day_number": 3,
                    "theme": "Departure",
                    "hotel": {"name": "Hotel C", "stars": 3, "price_per_night": 120, "amenities": ["Wi-Fi"], "description": "Hotel C description."},
                    "meals": [],
                    "attractions": [],
                    "activities": ["Checkout"],
                    "transport": {"mode": "Taxi", "estimated_cost": 200},
                    "estimated_day_cost": 1200,
                },
            ]
        ),
    )
    trip_id = created.json()["id"]

    def fake_generate(self, trip, day_number):
        return {
            "day_number": day_number,
            "theme": "Updated day two",
            "hotel": {
                "name": "Hotel B Updated",
                "stars": 4,
                "price_per_night": 180,
                "amenities": ["Wi-Fi", "Breakfast"],
                "description": "Updated hotel near the river.",
            },
            "meals": [],
            "attractions": [],
            "activities": ["Museum visit"],
            "transport": {"mode": "Taxi", "estimated_cost": 300},
            "estimated_day_cost": 2200,
        }

    monkeypatch.setattr("services.trip_service.TripService._generate_single_day", fake_generate)

    response = api_client.patch(f"/api/v1/trips/{trip_id}/days/2/regenerate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trip_id"] == trip_id
    assert payload["day_number"] == 2
    assert payload["regenerated_day"]["theme"] == "Updated day two"

    persisted = api_client.get(f"/api/v1/trips/{trip_id}")
    assert persisted.json()["itinerary"][1]["theme"] == "Updated day two"
    assert persisted.json()["itinerary"][0]["theme"] == "Arrival"
    assert persisted.json()["itinerary"][2]["theme"] == "Departure"


def test_patch_api_v1_trips_regenerate_day_returns_404_for_missing_trip(api_client):
    response = api_client.patch("/api/v1/trips/not-found/days/1/regenerate")

    assert response.status_code == 404
    assert response.json()["error"] == "Trip not found."


def test_patch_api_v1_trips_regenerate_day_returns_404_for_missing_day(api_client):
    created = api_client.post("/api/v1/trips", json=build_trip_payload())
    trip_id = created.json()["id"]

    response = api_client.patch(f"/api/v1/trips/{trip_id}/days/99/regenerate")

    assert response.status_code == 404
    assert response.json()["error"] == f"Day 99 not found for trip {trip_id}."


def test_patch_api_v1_trips_regenerate_day_returns_generic_error_on_ai_failure(api_client, monkeypatch):
    created = api_client.post(
        "/api/v1/trips",
        json=build_trip_payload(
            itinerary=[
                {
                    "day_number": 1,
                    "theme": "Arrival",
                    "hotel": {"name": "Hotel A", "stars": 3, "price_per_night": 100, "amenities": ["Wi-Fi"], "description": "Hotel A description."},
                    "meals": [],
                    "attractions": [],
                    "activities": ["Check-in"],
                    "transport": {"mode": "Taxi", "estimated_cost": 200},
                    "estimated_day_cost": 1000,
                },
                {
                    "day_number": 2,
                    "theme": "Culture",
                    "hotel": {"name": "Hotel B", "stars": 4, "price_per_night": 150, "amenities": ["Wi-Fi"], "description": "Hotel B description."},
                    "meals": [],
                    "attractions": [],
                    "activities": ["Museum"],
                    "transport": {"mode": "Taxi", "estimated_cost": 200},
                    "estimated_day_cost": 1500,
                },
                {
                    "day_number": 3,
                    "theme": "Departure",
                    "hotel": {"name": "Hotel C", "stars": 3, "price_per_night": 120, "amenities": ["Wi-Fi"], "description": "Hotel C description."},
                    "meals": [],
                    "attractions": [],
                    "activities": ["Checkout"],
                    "transport": {"mode": "Taxi", "estimated_cost": 200},
                    "estimated_day_cost": 1200,
                },
            ]
        ),
    )
    trip_id = created.json()["id"]

    def fake_generate(self, trip, day_number):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("services.trip_service.TripService._generate_single_day", fake_generate)

    response = api_client.patch(f"/api/v1/trips/{trip_id}/days/2/regenerate")

    assert response.status_code == 500
    assert response.json()["error"] == "Unable to generate the travel plan at this time. Please try again."

    persisted = api_client.get(f"/api/v1/trips/{trip_id}")
    assert persisted.status_code == 200
    assert persisted.json()["itinerary"][1]["theme"] == "Culture"


def test_post_api_v1_trips_rejects_missing_required_fields(api_client):
    response = api_client.post("/api/v1/trips", json={"destination": "Kyoto, Japan"})

    assert response.status_code == 422
