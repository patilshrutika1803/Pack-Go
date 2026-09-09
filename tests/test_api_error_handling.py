import importlib

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from models.schemas import (
    BudgetBreakdown,
    CategoryCost,
    CriticReview,
    DayPlan,
    Hotel,
    MealInfo,
    Transport,
    TravelPlan,
    UserPreferences,
    WeatherInfo,
)

import main


client = TestClient(main.app)


def test_unexpected_backend_exception_returns_generic_error(monkeypatch):
    def raise_runtime_error(self):
        raise RuntimeError("Provider payload leaked: api_key=abc123 secret=topsecret")

    monkeypatch.setattr(main.GraphBuilder, "build_graph", raise_runtime_error)

    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] == main.GENERIC_ERROR_MESSAGE
    assert "api_key" not in response.text.lower()
    assert "topsecret" not in response.text.lower()
    assert "Provider payload leaked" not in response.text


def test_raw_exception_details_are_not_exposed_in_response(monkeypatch):
    def raise_runtime_error(self):
        raise RuntimeError("Groq provider error: invalid authorization header")

    monkeypatch.setattr(main.GraphBuilder, "build_graph", raise_runtime_error)

    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 500
    assert response.json()["error"] == main.GENERIC_ERROR_MESSAGE
    assert "authorization header" not in response.text.lower()
    assert "Groq provider error" not in response.text


def test_sse_error_event_does_not_expose_raw_exception_details(monkeypatch):
    def raise_runtime_error(self):
        raise RuntimeError("raw stack trace or provider details should stay server-side")

    monkeypatch.setattr(main.GraphBuilder, "build_graph", raise_runtime_error)

    response = client.post("/plan/stream", json={"question": "Plan a trip"})

    assert response.status_code == 200
    body = "".join(response.iter_text())
    assert main.GENERIC_ERROR_MESSAGE in body
    assert "raw stack trace or provider details should stay server-side" not in body


def test_cors_allows_localhost_frontend_origin():
    response = client.options(
        "/plan",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_uses_explicit_origins_and_not_wildcard():
    cors_middleware = next(
        middleware for middleware in main.app.user_middleware if middleware.cls is CORSMiddleware
    )

    assert cors_middleware.kwargs["allow_credentials"] is True
    assert "*" not in cors_middleware.kwargs["allow_origins"]
    assert "http://localhost:5173" in cors_middleware.kwargs["allow_origins"]
    assert "http://127.0.0.1:5173" in cors_middleware.kwargs["allow_origins"]


def test_plan_persists_valid_travelplan_to_database(monkeypatch, tmp_path):
    db_file = tmp_path / "phase1d_plan.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    import database.connection as connection_module
    import database as database_module

    connection_module = importlib.reload(connection_module)
    database_module = importlib.reload(database_module)

    from database.base import Base
    Base.metadata.create_all(bind=connection_module.engine)

    import main as main_module
    main_module = importlib.reload(main_module)

    valid_plan = TravelPlan(
        preferences=UserPreferences(
            destination="Kyoto, Japan",
            duration=4,
            total_budget=1500.0,
            budget_currency="INR",
            travel_style="balanced",
            interests=["temples", "food"],
            things_to_avoid=["crowds"],
            group_size=2,
            travel_dates="2026-04-10 to 2026-04-14",
        ),
        weather=WeatherInfo(
            summary="Mild spring weather",
            temperature_range="15°C - 22°C",
            conditions="Sunny",
            packing_suggestions=["Light jacket"],
            travel_warnings=[],
            data_source="live_api",
            fallback_used=False,
        ),
        budget=BudgetBreakdown(
            total_estimated=1400.0,
            currency="INR",
            categories=[CategoryCost(name="Accommodation", amount=700.0)],
            is_within_budget=True,
            adjustment_suggestions=[],
        ),
        itinerary=[
            DayPlan(
                day_number=1,
                theme="Arrival and temples",
                hotel=Hotel(
                    name="Kiyomizu Inn",
                    stars=3,
                    price_per_night=120,
                    amenities=["Wi-Fi"],
                    description="Simple hotel near the city center.",
                ),
                meals=[
                    MealInfo(
                        meal_type="Breakfast",
                        restaurant_name="Cafe Matsu",
                        estimated_cost=250,
                    )
                ],
                attractions=[],
                activities=["Check-in", "Temple walk"],
                transport=Transport(mode="Taxi", estimated_cost=250),
                estimated_day_cost=2800,
            )
        ],
        critic_review=CriticReview(
            logical_flow_score=8.0,
            budget_alignment_score=8.5,
            weather_suitability_score=8.0,
            preference_match_score=9.0,
            overall_score=8.5,
            warnings=[],
            highlights=["Good pace"],
            requires_revision=False,
            revision_instructions=[],
        ),
        revision_history=[],
        data_freshness={"weather": "live", "budget": "live"},
    )

    class FakeGraph:
        def invoke(self, payload, config):
            return {
                "messages": payload.get("messages", []),
                "intent": "plan_trip",
                "preferences": valid_plan.preferences,
                "weather_info": valid_plan.weather,
                "budget_breakdown": valid_plan.budget,
                "itinerary": valid_plan.itinerary,
                "critic_review": valid_plan.critic_review,
                "revision_history": valid_plan.revision_history,
                "data_freshness": valid_plan.data_freshness,
                "failed_agents": [],
                "failure_reasons": {},
            }

    monkeypatch.setattr(main_module.GraphBuilder, "build_graph", lambda self: FakeGraph())

    client = TestClient(main_module.app)
    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 200
    assert response.json()["state"] == "complete"
    assert response.json()["plan"].get("preferences", {}).get("destination") == "Kyoto, Japan"

    from services.trip_service import TripService

    trips = TripService().list_trips()
    assert len(trips) == 1
    assert trips[0].destination == "Kyoto, Japan"
    assert trips[0].title == "Kyoto, Japan"
    assert trips[0].travel_style == "balanced"


def test_plan_does_not_persist_invalid_workflow_output(monkeypatch, tmp_path):
    db_file = tmp_path / "phase1d_invalid.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    import database.connection as connection_module
    import database as database_module

    connection_module = importlib.reload(connection_module)
    database_module = importlib.reload(database_module)

    from database.base import Base
    Base.metadata.create_all(bind=connection_module.engine)

    import main as main_module
    main_module = importlib.reload(main_module)

    class FakeGraph:
        def invoke(self, payload, config):
            return {
                "messages": payload.get("messages", []),
                "intent": "plan_trip",
                "preferences": UserPreferences(
                    destination="Paris, France",
                    duration=2,
                    total_budget=500.0,
                    budget_currency="EUR",
                    travel_style="budget",
                ),
                "budget_breakdown": BudgetBreakdown(
                    total_estimated=450.0,
                    currency="EUR",
                    categories=[],
                    is_within_budget=True,
                    adjustment_suggestions=[],
                ),
                "itinerary": [],
                "critic_review": None,
                "failed_agents": [],
                "failure_reasons": {},
                "data_freshness": {},
            }

    monkeypatch.setattr(main_module.GraphBuilder, "build_graph", lambda self: FakeGraph())

    from services.trip_service import TripService

    client = TestClient(main_module.app)
    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 422
    assert len(TripService().list_trips()) == 0


def test_plan_db_failure_does_not_expose_raw_database_error(monkeypatch, tmp_path):
    db_file = tmp_path / "phase1d_db_failure.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    import database.connection as connection_module
    import database as database_module

    connection_module = importlib.reload(connection_module)
    database_module = importlib.reload(database_module)

    from database.base import Base
    Base.metadata.create_all(bind=connection_module.engine)

    import main as main_module
    main_module = importlib.reload(main_module)

    valid_plan = TravelPlan(
        preferences=UserPreferences(
            destination="Bali, Indonesia",
            duration=3,
            total_budget=900.0,
            budget_currency="INR",
            travel_style="relaxed",
        ),
        weather=WeatherInfo(
            summary="Warm tropical weather",
            temperature_range="25°C - 30°C",
            conditions="Sunny",
            data_source="live_api",
        ),
        budget=BudgetBreakdown(
            total_estimated=850.0,
            currency="INR",
            categories=[],
            is_within_budget=True,
            adjustment_suggestions=[],
        ),
        itinerary=[
            DayPlan(
                day_number=1,
                theme="Beach day",
                hotel=Hotel(
                    name="Bali Stay",
                    stars=4,
                    price_per_night=100,
                    description="Comfortable stay",
                ),
                meals=[MealInfo(meal_type="Lunch", restaurant_name="Beach Cafe", estimated_cost=300)],
                attractions=[],
                activities=[],
                transport=Transport(mode="Taxi", estimated_cost=150),
                estimated_day_cost=1500,
            )
        ],
        critic_review=CriticReview(
            logical_flow_score=8.0,
            budget_alignment_score=8.0,
            weather_suitability_score=8.5,
            preference_match_score=8.0,
            overall_score=8.3,
            warnings=[],
            highlights=[],
            requires_revision=False,
            revision_instructions=[],
        ),
        revision_history=[],
        data_freshness={"weather": "live"},
    )

    class FakeGraph:
        def invoke(self, payload, config):
            return {
                "messages": payload.get("messages", []),
                "intent": "plan_trip",
                "preferences": valid_plan.preferences,
                "weather_info": valid_plan.weather,
                "budget_breakdown": valid_plan.budget,
                "itinerary": valid_plan.itinerary,
                "critic_review": valid_plan.critic_review,
                "revision_history": valid_plan.revision_history,
                "data_freshness": valid_plan.data_freshness,
                "failed_agents": [],
                "failure_reasons": {},
            }

    monkeypatch.setattr(main_module.GraphBuilder, "build_graph", lambda self: FakeGraph())

    from services.trip_service import TripService

    def raise_db_error(self, travel_plan):
        raise RuntimeError("database exploded")

    monkeypatch.setattr(TripService, "create_trip", raise_db_error)

    client = TestClient(main_module.app)
    response = client.post("/plan", json={"question": "Plan a trip"})

    assert response.status_code == 500
    assert response.json()["error"] == main_module.GENERIC_ERROR_MESSAGE
    assert "database exploded" not in response.text.lower()
    assert len(TripService().list_trips()) == 0
