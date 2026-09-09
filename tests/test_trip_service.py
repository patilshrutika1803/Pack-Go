import importlib
from datetime import UTC, datetime

import pytest

from models.schemas import (
    BudgetBreakdown,
    CategoryCost,
    CriticReview,
    DayPlan,
    Hotel,
    MealInfo,
    RevisionRecord,
    Transport,
    TravelPlan,
    UserPreferences,
    WeatherInfo,
)


@pytest.fixture
def isolated_trip_service(tmp_path, monkeypatch):
    db_file = tmp_path / "trip_service_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    import database.connection as connection_module
    import database as database_module

    connection_module = importlib.reload(connection_module)
    database_module = importlib.reload(database_module)

    from database.base import Base

    Base.metadata.create_all(bind=connection_module.engine)

    import services.trip_service as trip_service_module

    trip_service_module = importlib.reload(trip_service_module)

    return trip_service_module.TripService()


@pytest.fixture
def representative_travel_plan():
    return TravelPlan(
        preferences=UserPreferences(
            destination="Kyoto, Japan",
            duration=7,
            total_budget=1800.0,
            budget_currency="INR",
            travel_style="balanced",
            interests=["temples", "food", "culture"],
            things_to_avoid=["crowded areas"],
            group_size=2,
            travel_dates="2026-04-10 to 2026-04-17",
        ),
        weather=WeatherInfo(
            summary="Mild spring weather",
            temperature_range="15°C - 22°C",
            conditions="Sunny",
            packing_suggestions=["Light jacket", "Walking shoes"],
            travel_warnings=[],
            data_source="live_api",
            fallback_used=False,
        ),
        budget=BudgetBreakdown(
            total_estimated=1750.0,
            currency="INR",
            categories=[
                CategoryCost(name="Accommodation", amount=700.0),
                CategoryCost(name="Food", amount=420.0),
            ],
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
                    amenities=["Wi-Fi", "Breakfast"],
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
            overall_score=8.5,
            logical_flow_score=8.0,
            budget_alignment_score=8.5,
            weather_suitability_score=8.0,
            preference_match_score=9.0,
            warnings=[],
            highlights=["Good pace"],
            requires_revision=False,
            revision_instructions=[],
        ),
        revision_history=[
            RevisionRecord(iteration=1, score=8.5, changes_made="Initial itinerary drafted."),
        ],
        data_freshness={"weather": "live", "budget": "live"},
        generated_at=datetime.now(UTC),
    )


def test_create_trip_success_and_generates_id(isolated_trip_service, representative_travel_plan):
    created_trip = isolated_trip_service.create_trip(representative_travel_plan)

    assert created_trip is not None
    assert created_trip.id
    assert created_trip.destination == "Kyoto, Japan"
    assert created_trip.duration == 7
    assert created_trip.total_budget == 1800.0


def test_get_trip_returns_persisted_trip(isolated_trip_service, representative_travel_plan):
    created_trip = isolated_trip_service.create_trip(representative_travel_plan)

    fetched_trip = isolated_trip_service.get_trip(created_trip.id)

    assert fetched_trip is not None
    assert fetched_trip.id == created_trip.id
    assert fetched_trip.title == "Kyoto, Japan"
    assert fetched_trip.interests == ["temples", "food", "culture"]
    assert fetched_trip.budget_currency == "INR"


def test_list_trips_returns_newest_first(isolated_trip_service, representative_travel_plan):
    first_trip = isolated_trip_service.create_trip(representative_travel_plan)

    second_travel_plan = representative_travel_plan.model_copy()
    second_travel_plan.preferences = second_travel_plan.preferences.model_copy(update={"destination": "Paris, France"})
    second_trip = isolated_trip_service.create_trip(second_travel_plan)

    trips = isolated_trip_service.list_trips()

    assert [trip.id for trip in trips] == [second_trip.id, first_trip.id]


def test_update_trip_supports_partial_updates(isolated_trip_service, representative_travel_plan):
    created_trip = isolated_trip_service.create_trip(representative_travel_plan)

    updated_trip = isolated_trip_service.update_trip(
        created_trip.id,
        {
            "destination": "Kyoto, Japan - Updated",
            "travel_style": "luxury",
        },
    )

    assert updated_trip is not None
    assert updated_trip.destination == "Kyoto, Japan - Updated"
    assert updated_trip.travel_style == "luxury"
    assert updated_trip.interests == ["temples", "food", "culture"]
    assert updated_trip.updated_at >= created_trip.updated_at


def test_delete_trip_removes_trip(isolated_trip_service, representative_travel_plan):
    created_trip = isolated_trip_service.create_trip(representative_travel_plan)

    deleted = isolated_trip_service.delete_trip(created_trip.id)

    assert deleted is True
    assert isolated_trip_service.get_trip(created_trip.id) is None


def test_travelplan_conversion_round_trip(isolated_trip_service, representative_travel_plan):
    converted_trip = isolated_trip_service.travelplan_to_trip(representative_travel_plan, trip_id="fixture-trip-id")

    assert converted_trip.id == "fixture-trip-id"
    assert converted_trip.destination == "Kyoto, Japan"
    assert converted_trip.budget_breakdown is not None
    assert converted_trip.weather is not None

    converted_plan = isolated_trip_service.trip_to_travelplan(converted_trip)

    assert converted_plan.preferences is not None
    assert converted_plan.preferences.destination == "Kyoto, Japan"
    assert converted_plan.data_freshness == {"weather": "live", "budget": "live"}
