import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "api_v1_utilities.db"
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
    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    registration = client.post(
        "/api/v1/auth/register",
        json={"name": "Utility Tester", "email": "utility-tester@example.com", "password": "password123"},
    )
    client.headers.update({"Authorization": f"Bearer {registration.json()['access_token']}"})
    return client

from test_api_trip_crud import build_trip_payload


def test_trip_utilities_are_access_controlled_and_build_packing_data(api_client):
    created = api_client.post(
        "/api/v1/trips",
        json=build_trip_payload(
            interests=["beach", "nature"],
            weather={"conditions": "rain showers", "packing_suggestions": ["Rain jacket"]},
            itinerary=[{"day_number": 1, "attractions": [{"place": {"name": "Fushimi Inari"}}]}],
        ),
    ).json()

    response = api_client.get(f"/api/v1/trips/{created['id']}/utilities/packing")
    assert response.status_code == 200
    assert "Rain jacket" in response.json()["items"]
    assert "Swimwear and sun protection" in response.json()["items"]
    assert "Rain jacket" in response.json()["categories"]["clothing"]
    assert "Umbrella or raincoat" in response.json()["categories"]["weather"]
    assert "Swimwear and sun protection" in response.json()["categories"]["destination"]

    map_response = api_client.get(f"/api/v1/trips/{created['id']}/utilities/map")
    assert map_response.status_code == 200
    assert map_response.json()["locations"][1]["name"] == "Fushimi Inari"
    assert "openstreetmap.org/search" in map_response.json()["locations"][1]["search_url"]

    api_client.headers.update({"Authorization": "Bearer invalid-token"})
    assert api_client.get(f"/api/v1/trips/{created['id']}/utilities/packing").status_code == 401


def test_trip_utilities_hide_missing_and_foreign_trips(api_client):
    created = api_client.post("/api/v1/trips", json=build_trip_payload()).json()
    assert api_client.get("/api/v1/trips/not-a-trip/utilities/map").status_code == 404

    owner_headers = dict(api_client.headers)
    registration = api_client.post(
        "/api/v1/auth/register",
        json={"name": "Other User", "email": "other-utility-user@example.com", "password": "password123"},
    ).json()
    api_client.headers.update({"Authorization": f"Bearer {registration['access_token']}"})
    assert api_client.get(f"/api/v1/trips/{created['id']}/utilities/packing").status_code == 404
    assert api_client.get(f"/api/v1/trips/{created['id']}/utilities/map").status_code == 404
    api_client.headers.update(owner_headers)


def test_currency_route_uses_retrieved_rate(monkeypatch, api_client):
    class FakeCurrencyService:
        def convert(self, amount, source, target):
            assert (amount, source, target) == (10, "USD", "INR")
            return 830

    monkeypatch.setattr("api.v1.utilities.CurrencyConverterTool", lambda: SimpleNamespace(currency_service=FakeCurrencyService()))
    response = api_client.get("/api/v1/utilities/currency?amount=10&from_currency=usd&to_currency=inr")
    assert response.status_code == 200
    assert response.json()["converted_amount"] == 830
    assert response.json()["rate"] == 83
    assert response.json()["source"] == "ExchangeRate-API"
    assert response.json()["status"] == "success"


def test_currency_rejects_nonpositive_or_nonfinite_amounts(api_client):
    for amount in ("0", "-1", "nan", "inf"):
        response = api_client.get(f"/api/v1/utilities/currency?amount={amount}&from_currency=USD&to_currency=INR")
        assert response.status_code == 422


def test_currency_provider_timeout_is_safe(monkeypatch, api_client):
    class TimedOutCurrencyService:
        def convert(self, amount, source, target):
            raise TimeoutError("provider timeout details must not leak")

    monkeypatch.setattr("api.v1.utilities.CurrencyConverterTool", lambda: SimpleNamespace(currency_service=TimedOutCurrencyService()))
    response = api_client.get("/api/v1/utilities/currency?amount=10&from_currency=USD&to_currency=INR")
    assert response.status_code == 502
    assert response.json()["error"] == "Currency provider is temporarily unavailable."


def test_places_success_and_provider_failure_are_safe(monkeypatch, api_client):
    class PlaceSearch:
        def tavily_search_attractions(self, location):
            assert location == "Kyoto"
            return "Kiyomizu-dera"

    monkeypatch.setattr("api.v1.utilities.PlaceSearchTool", lambda: SimpleNamespace(tavily_search=PlaceSearch()))
    response = api_client.get("/api/v1/utilities/places?location=Kyoto&category=attractions")
    assert response.status_code == 200
    assert response.json()["results"] == "Kiyomizu-dera"
    assert response.json()["status"] == "success"

    class FailingPlaceSearch:
        def tavily_search_attractions(self, location):
            raise TimeoutError("provider timeout details must not leak")

    monkeypatch.setattr("api.v1.utilities.PlaceSearchTool", lambda: SimpleNamespace(tavily_search=FailingPlaceSearch()))
    failed = api_client.get("/api/v1/utilities/places?location=Kyoto&category=attractions")
    assert failed.status_code == 502
    assert failed.json()["error"] == "Place provider is temporarily unavailable."


def test_utility_provider_failures_are_safe(monkeypatch, api_client):
    for error_type in (RuntimeError, TimeoutError):
        class FailingWeather:
            def get_current_weather_info(self, location):
                raise error_type("provider details must not leak")

        monkeypatch.setattr("api.v1.utilities.WeatherInfoTool", FailingWeather)
        response = api_client.get("/api/v1/utilities/weather?location=Kyoto")
        assert response.status_code == 502
        assert response.json()["error"] == "Weather provider is temporarily unavailable."


def test_weather_success_and_blank_location_validation(monkeypatch, api_client):
    weather = SimpleNamespace(
        model_dump=lambda: {
            "summary": "Current weather in Kyoto: clear sky.",
            "temperature_range": "18°C",
            "conditions": "clear sky",
            "packing_suggestions": [],
            "travel_warnings": [],
            "data_source": "live_api",
            "fallback_used": False,
        }
    )

    class WorkingWeather:
        def get_current_weather_info(self, location):
            assert location == "Kyoto"
            return weather

    monkeypatch.setattr("api.v1.utilities.WeatherInfoTool", WorkingWeather)
    response = api_client.get("/api/v1/utilities/weather?location=%20Kyoto%20")
    assert response.status_code == 200
    assert response.json()["data_source"] == "live_api"
    assert api_client.get("/api/v1/utilities/weather?location=%20%20").status_code == 422


def test_currency_invalid_code_and_bad_provider_result_are_safe(monkeypatch, api_client):
    invalid = api_client.get("/api/v1/utilities/currency?amount=10&from_currency=1SD&to_currency=INR")
    assert invalid.status_code == 422

    class BadCurrencyService:
        def convert(self, amount, source, target):
            return float("nan")

    monkeypatch.setattr("api.v1.utilities.CurrencyConverterTool", lambda: SimpleNamespace(currency_service=BadCurrencyService()))
    failed = api_client.get("/api/v1/utilities/currency?amount=10&from_currency=USD&to_currency=INR")
    assert failed.status_code == 502
    assert failed.json()["error"] == "Currency provider is temporarily unavailable."