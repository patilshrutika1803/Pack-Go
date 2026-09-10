from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import Trip
from models.schemas import (
    BudgetBreakdown,
    CriticReview,
    DayPlan,
    RevisionRecord,
    TravelPlan,
    UserPreferences,
    WeatherInfo,
)


class TripNotFoundError(Exception):
    """Raised when a trip cannot be found."""


class DayNotFoundError(Exception):
    """Raised when a day number is not present in an itinerary."""


class DayRegenerationError(Exception):
    """Raised when the single-day regeneration process fails."""


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
        from database.connection import SessionLocal

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

    def get_trip(self, trip_id: str, user_id: str | None = None) -> Trip | None:
        from database.connection import SessionLocal

        session = SessionLocal()

        try:
            statement = select(Trip).where(Trip.id == trip_id)
            if user_id is not None:
                statement = statement.where(Trip.user_id == user_id)
            return session.scalar(statement)
        except SQLAlchemyError as exc:
            raise RuntimeError("Failed to retrieve trip.") from exc
        finally:
            session.close()

    def list_trips(self, user_id: str | None = None) -> list[Trip]:
        from database.connection import SessionLocal

        session = SessionLocal()

        try:
            statement = select(Trip).order_by(Trip.created_at.desc(), Trip.id.desc())
            if user_id is not None:
                statement = statement.where(Trip.user_id == user_id)
            return list(session.scalars(statement).all())
        except SQLAlchemyError as exc:
            raise RuntimeError("Failed to list trips.") from exc
        finally:
            session.close()

    def update_trip(self, trip_id: str, updates: dict[str, Any] | None, user_id: str | None = None) -> Trip | None:
        if not updates:
            return self.get_trip(trip_id, user_id=user_id)

        from database.connection import SessionLocal

        session = SessionLocal()

        try:
            statement = select(Trip).where(Trip.id == trip_id)
            if user_id is not None:
                statement = statement.where(Trip.user_id == user_id)
            trip = session.scalar(statement)
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

    def delete_trip(self, trip_id: str, user_id: str | None = None) -> bool:
        from database.connection import SessionLocal

        session = SessionLocal()

        try:
            statement = select(Trip).where(Trip.id == trip_id)
            if user_id is not None:
                statement = statement.where(Trip.user_id == user_id)
            trip = session.scalar(statement)
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

    def regenerate_day(self, trip_id: str, day_number: int, user_id: str | None = None) -> dict[str, Any]:
        from database.connection import SessionLocal

        session = SessionLocal()

        try:
            statement = select(Trip).where(Trip.id == trip_id)
            if user_id is not None:
                statement = statement.where(Trip.user_id == user_id)
            trip = session.scalar(statement)
            if trip is None:
                raise TripNotFoundError(f"Trip {trip_id} was not found.")

            itinerary = list(trip.itinerary or [])
            if day_number < 1 or day_number > len(itinerary):
                raise DayNotFoundError(f"Day {day_number} not found for trip {trip_id}.")

            replacement_day = self._generate_single_day(trip, day_number)
            replacement_day = DayPlan.model_validate(replacement_day)
            replacement_day.day_number = day_number

            itinerary[day_number - 1] = self._normalize_json_value(replacement_day.model_dump(mode="json"))
            trip.itinerary = itinerary

            revision_history = list(trip.revision_history or [])
            revision_history.append(
                {
                    "iteration": len(revision_history) + 1,
                    "score": 0,
                    "changes_made": f"Regenerated day {day_number}.",
                }
            )
            trip.revision_history = revision_history
            trip.updated_at = self._next_timestamp()

            session.commit()
            session.refresh(trip)

            return {
                "trip_id": trip.id,
                "day_number": day_number,
                "regenerated_day": self._normalize_json_value(trip.itinerary[day_number - 1]),
                "updated_at": trip.updated_at,
            }
        except (TripNotFoundError, DayNotFoundError):
            session.rollback()
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            raise RuntimeError("Failed to regenerate trip day.") from exc
        except Exception as exc:
            session.rollback()
            raise RuntimeError("Failed to regenerate trip day.") from exc
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

    def _generate_single_day(self, trip: Trip, day_number: int) -> dict[str, Any]:
        """
        Generate exactly one replacement day using the existing LLM configuration,
        while leaving the rest of the trip untouched.

        The existing LangGraph workflow is intentionally left unchanged. This service-level
        implementation reuses the established structured-output LLM utilities and the same
        itinerary schema, but targets only a single day instead of regenerating the full
        itinerary.
        """
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

        day_context = self._normalize_json_value(trip.itinerary[day_number - 1] if trip.itinerary else {})

        content = (
            f"Destination: {preferences.destination}\n"
            f"Trip duration: {preferences.duration} days\n"
            f"Travel style: {preferences.travel_style}\n"
            f"Group size: {preferences.group_size}\n"
            f"Interests: {', '.join(preferences.interests) if preferences.interests else 'General'}\n"
            f"Things to avoid: {', '.join(preferences.things_to_avoid) if preferences.things_to_avoid else 'None'}\n"
            f"Current weather: {trip.weather}\n"
            f"Current budget: {trip.budget_breakdown}\n"
            f"Existing day {day_number} context:\n{day_context}\n"
            f"Regenerate only day {day_number}. Preserve every other itinerary day exactly as-is."
        )

        system_prompt = (
            f"{ITINERARY_SYSTEM_PROMPT}\n\n"
            "You are regenerating exactly one itinerary day for an existing trip. "
            "Return a one-item itinerary list containing only the replacement for day_number "
            f"{day_number}. Do not regenerate or modify any other days."
        )

        def build_chain(llm):
            return build_structured_output(llm, ItineraryOutput)

        response = invoke_with_fallback(
            build_chain,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content),
            ],
        )

        if not getattr(response, "itinerary", None):
            raise DayRegenerationError("No itinerary day was generated.")

        generated_day = response.itinerary[0]
        generated_day.day_number = day_number
        return self._normalize_json_value(generated_day.model_dump(mode="json"))

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
