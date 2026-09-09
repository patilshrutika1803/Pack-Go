from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal, Trip
from models.schemas import (
    BudgetBreakdown,
    CriticReview,
    DayPlan,
    RevisionRecord,
    TravelPlan,
    UserPreferences,
    WeatherInfo,
)


class TripService:
    """CRUD service for persisting and retrieving PACK & GO trip plans."""

    def __init__(self):
        self._last_timestamp: datetime | None = None

    def create_trip(
        self,
        travel_plan: TravelPlan | Trip | dict[str, Any] | None,
        trip_id: str | None = None,
    ) -> Trip:
        """Create a trip from a TravelPlan or an existing Trip instance."""
        trip = self._normalize_trip_input(travel_plan, trip_id)
        session = SessionLocal()

        try:
            session.add(trip)
            session.commit()
            session.refresh(trip)
            return trip
        except SQLAlchemyError as exc:
            session.rollback()
            raise RuntimeError("Failed to create trip.") from exc
        finally:
            session.close()

    def get_trip(self, trip_id: str) -> Trip | None:
        session = SessionLocal()

        try:
            return session.get(Trip, trip_id)
        except SQLAlchemyError as exc:
            raise RuntimeError("Failed to retrieve trip.") from exc
        finally:
            session.close()

    def list_trips(self) -> list[Trip]:
        session = SessionLocal()

        try:
            statement = select(Trip).order_by(Trip.created_at.desc(), Trip.id.desc())
            return list(session.scalars(statement).all())
        except SQLAlchemyError as exc:
            raise RuntimeError("Failed to list trips.") from exc
        finally:
            session.close()

    def update_trip(self, trip_id: str, updates: dict[str, Any] | None) -> Trip | None:
        if not updates:
            return self.get_trip(trip_id)

        session = SessionLocal()

        try:
            trip = session.get(Trip, trip_id)
            if trip is None:
                return None

            for key, value in updates.items():
                if key in {"id", "created_at", "updated_at"}:
                    continue
                if hasattr(Trip, key):
                    setattr(trip, key, value)

            trip.updated_at = self._next_timestamp()
            session.commit()
            session.refresh(trip)
            return trip
        except SQLAlchemyError as exc:
            session.rollback()
            raise RuntimeError("Failed to update trip.") from exc
        finally:
            session.close()

    def delete_trip(self, trip_id: str) -> bool:
        session = SessionLocal()

        try:
            trip = session.get(Trip, trip_id)
            if trip is None:
                return False

            session.delete(trip)
            session.commit()
            return True
        except SQLAlchemyError as exc:
            session.rollback()
            raise RuntimeError("Failed to delete trip.") from exc
        finally:
            session.close()

    def travelplan_to_trip(
        self,
        travel_plan: TravelPlan | dict[str, Any],
        trip_id: str | None = None,
    ) -> Trip:
        if isinstance(travel_plan, dict):
            travel_plan = TravelPlan.model_validate(travel_plan)

        preferences = travel_plan.preferences
        weather = travel_plan.weather
        budget = travel_plan.budget
        critic_review = travel_plan.critic_review

        created_at = self._next_timestamp()

        return Trip(
            id=trip_id or str(uuid4()),
            title=(preferences.destination if preferences and preferences.destination else "Untitled Trip"),
            destination=(preferences.destination if preferences and preferences.destination else ""),
            duration=(preferences.duration if preferences else 0),
            total_budget=(preferences.total_budget if preferences else 0.0),
            budget_currency=(preferences.budget_currency if preferences else "INR"),
            group_size=(preferences.group_size if preferences else 1),
            travel_style=(preferences.travel_style if preferences else "balanced"),
            travel_dates=(preferences.travel_dates if preferences else None),
            interests=(list(preferences.interests) if preferences and preferences.interests else []),
            things_to_avoid=(list(preferences.things_to_avoid) if preferences and preferences.things_to_avoid else []),
            itinerary=[self._normalize_json_value(item) for item in travel_plan.itinerary],
            weather=self._normalize_json_value(weather.model_dump(mode="json")) if weather else None,
            budget_breakdown=self._normalize_json_value(budget.model_dump(mode="json")) if budget else None,
            critic_review=self._normalize_json_value(critic_review.model_dump(mode="json")) if critic_review else None,
            revision_history=[self._normalize_json_value(item) for item in travel_plan.revision_history],
            data_freshness=self._normalize_json_value(travel_plan.data_freshness or {}),
            original_query=None,
            created_at=created_at,
            updated_at=created_at,
        )

    def trip_to_travelplan(self, trip: Trip) -> TravelPlan:
        preferences = UserPreferences(
            destination=trip.destination,
            duration=trip.duration,
            total_budget=trip.total_budget,
            budget_currency=trip.budget_currency,
            travel_style=trip.travel_style,
            interests=list(trip.interests or []),
            things_to_avoid=list(trip.things_to_avoid or []),
            group_size=trip.group_size,
            travel_dates=trip.travel_dates,
        )

        itinerary = [DayPlan.model_validate(day) for day in trip.itinerary or []]
        revision_history = [RevisionRecord.model_validate(item) for item in trip.revision_history or []]

        return TravelPlan(
            preferences=preferences,
            weather=(WeatherInfo.model_validate(trip.weather) if trip.weather else None),
            budget=(BudgetBreakdown.model_validate(trip.budget_breakdown) if trip.budget_breakdown else None),
            itinerary=itinerary,
            critic_review=(CriticReview.model_validate(trip.critic_review) if trip.critic_review else None),
            revision_history=revision_history,
            data_freshness=dict(trip.data_freshness or {}),
            generated_at=self._ensure_utc_datetime(trip.updated_at or trip.created_at),
        )

    def _normalize_trip_input(
        self,
        travel_plan: TravelPlan | Trip | dict[str, Any] | None,
        trip_id: str | None,
    ) -> Trip:
        if isinstance(travel_plan, Trip):
            trip = travel_plan
            if trip_id and trip.id is None:
                trip.id = trip_id
            if trip.id is None:
                trip.id = str(uuid4())
            trip.created_at = self._ensure_utc_datetime(trip.created_at or self._next_timestamp())
            trip.updated_at = self._ensure_utc_datetime(trip.updated_at or trip.created_at)
            return trip

        if travel_plan is None:
            raise ValueError("A TravelPlan or Trip object is required.")

        return self.travelplan_to_trip(travel_plan, trip_id=trip_id)

    @staticmethod
    def _normalize_json_value(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: TripService._normalize_json_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [TripService._normalize_json_value(item) for item in value]
        return value

    @staticmethod
    def _ensure_utc_datetime(value: datetime | None) -> datetime:
        if value is None:
            return TripService._utc_now()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _next_timestamp(self) -> datetime:
        now = datetime.now(UTC)

        if self._last_timestamp is not None and now <= self._last_timestamp:
            now = self._last_timestamp + timedelta(microseconds=1)

        self._last_timestamp = now
        return now

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)
