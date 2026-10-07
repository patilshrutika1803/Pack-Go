from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database
from langchain_core.messages import HumanMessage, SystemMessage

from models.schemas import (
    BudgetBreakdown,
    CriticReview,
    DayPlan,
    RevisionRecord,
    TravelPlan,
    UserPreferences,
    WeatherInfo,
)
from agent.itinerary_agent import ItineraryOutput
from prompt_library.itinerary_prompt import SYSTEM_PROMPT as ITINERARY_SYSTEM_PROMPT
from utils.llm_loader import build_structured_output, invoke_with_fallback


class TripNotFoundError(Exception):
    """Raised when a trip cannot be found."""


class DayNotFoundError(Exception):
    """Raised when a day number is not present in an itinerary."""


class DayRegenerationError(Exception):
    """Raised when the single-day regeneration process fails."""


class TripService:
    """CRUD service for persistent MongoDB trip documents."""

    def __init__(self, database: Database):
        self.database = database
        self._last_timestamp: datetime | None = None

    def create_trip(
        self,
        travel_plan: TravelPlan | dict[str, Any] | None,
        trip_id: str | None = None,
    ) -> dict[str, Any]:
        trip = self._normalize_trip_input(travel_plan, trip_id)
        self.database.trips.insert_one(trip)
        return trip

    def get_trip(self, trip_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        query: dict[str, Any] = {"_id": trip_id}
        if user_id is not None:
            query["user_id"] = user_id
        return self.database.trips.find_one(query)

    def list_trips(self, user_id: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {} if user_id is None else {"user_id": user_id}
        return list(self.database.trips.find(query).sort([("created_at", -1), ("_id", -1)]))

    def update_trip(self, trip_id: str, updates: dict[str, Any] | None, user_id: str | None = None) -> dict[str, Any] | None:
        if not updates:
            return self.get_trip(trip_id, user_id=user_id)
        query: dict[str, Any] = {"_id": trip_id}
        if user_id is not None:
            query["user_id"] = user_id
        allowed_fields = {
            "title", "destination", "duration", "total_budget", "budget_currency",
            "group_size", "travel_style", "travel_dates", "interests",
            "things_to_avoid", "itinerary", "weather", "budget_breakdown",
            "critic_review", "revision_history", "data_freshness", "original_query",
        }
        changes = {key: value for key, value in updates.items() if key in allowed_fields}
        changes["updated_at"] = self._next_timestamp()
        return self.database.trips.find_one_and_update(
            query,
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )

    def delete_trip(self, trip_id: str, user_id: str | None = None) -> bool:
        query: dict[str, Any] = {"_id": trip_id}
        if user_id is not None:
            query["user_id"] = user_id
        result = self.database.trips.delete_one(query)
        if result.deleted_count:
            for collection in ("trip_messages", "expenses", "journal_entries", "notifications"):
                self.database[collection].delete_many({"trip_id": trip_id})
        return result.deleted_count == 1

    def regenerate_day(self, trip_id: str, day_number: int, user_id: str | None = None) -> dict[str, Any]:
        trip = self.get_trip(trip_id, user_id=user_id)
        if trip is None:
            raise TripNotFoundError(f"Trip {trip_id} was not found.")

        itinerary = list(trip.get("itinerary") or [])
        if day_number < 1 or day_number > len(itinerary):
            raise DayNotFoundError(f"Day {day_number} not found for trip {trip_id}.")

        try:
            replacement_day = DayPlan.model_validate(self._generate_single_day(trip, day_number))
            replacement_day.day_number = day_number
            itinerary[day_number - 1] = self._normalize_json_value(replacement_day.model_dump(mode="json"))
            revision_history = list(trip.get("revision_history") or [])
            revision_history.append({
                "iteration": len(revision_history) + 1,
                "score": 0,
                "changes_made": f"Regenerated day {day_number}.",
            })
            updated_at = self._next_timestamp()
            result = self.database.trips.update_one(
                {"_id": trip_id, **({"user_id": user_id} if user_id is not None else {})},
                {"$set": {"itinerary": itinerary, "revision_history": revision_history, "updated_at": updated_at}},
            )
            if result.matched_count != 1:
                raise TripNotFoundError(f"Trip {trip_id} was not found.")
        except (TripNotFoundError, DayNotFoundError):
            raise
        except Exception as exc:
            raise RuntimeError("Failed to regenerate trip day.") from exc
        return {
            "trip_id": trip_id,
            "day_number": day_number,
            "regenerated_day": itinerary[day_number - 1],
            "updated_at": updated_at,
        }

    def travelplan_to_trip(
        self,
        travel_plan: TravelPlan | dict[str, Any],
        trip_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if isinstance(travel_plan, dict):
            travel_plan = TravelPlan.model_validate(travel_plan)

        preferences = travel_plan.preferences
        weather = travel_plan.weather
        budget = travel_plan.budget
        critic_review = travel_plan.critic_review
        created_at = self._next_timestamp()
        identifier = trip_id or str(uuid4())
        return {
            "_id": identifier,
            "id": identifier,
            "user_id": user_id,
            "is_group": False,
            "title": preferences.destination if preferences and preferences.destination else "Untitled Trip",
            "destination": preferences.destination if preferences and preferences.destination else "",
            "duration": preferences.duration if preferences else 0,
            "total_budget": preferences.total_budget if preferences else 0.0,
            "budget_currency": preferences.budget_currency if preferences else "INR",
            "group_size": preferences.group_size if preferences else 1,
            "travel_style": preferences.travel_style if preferences else "balanced",
            "travel_dates": preferences.travel_dates if preferences else None,
            "interests": list(preferences.interests) if preferences and preferences.interests else [],
            "things_to_avoid": list(preferences.things_to_avoid) if preferences and preferences.things_to_avoid else [],
            "itinerary": [self._normalize_json_value(item) for item in travel_plan.itinerary],
            "weather": self._normalize_json_value(weather.model_dump(mode="json")) if weather else None,
            "budget_breakdown": self._normalize_json_value(budget.model_dump(mode="json")) if budget else None,
            "critic_review": self._normalize_json_value(critic_review.model_dump(mode="json")) if critic_review else None,
            "revision_history": [self._normalize_json_value(item) for item in travel_plan.revision_history],
            "data_freshness": self._normalize_json_value(travel_plan.data_freshness or {}),
            "original_query": None,
            "members": [],
            "invitations": [],
            "proposals": [],
            "decisions": [],
            "checklist_items": [],
            "created_at": created_at,
            "updated_at": created_at,
        }

    def _generate_single_day(self, trip: dict[str, Any], day_number: int) -> dict[str, Any]:
        preferences = UserPreferences(
            destination=trip["destination"],
            duration=trip["duration"],
            total_budget=trip["total_budget"],
            budget_currency=trip["budget_currency"],
            travel_style=trip["travel_style"],
            interests=list(trip.get("interests") or []),
            things_to_avoid=list(trip.get("things_to_avoid") or []),
            group_size=trip["group_size"],
            travel_dates=trip.get("travel_dates"),
        )
        day_context = self._normalize_json_value((trip.get("itinerary") or [])[day_number - 1])
        content = (
            f"Destination: {preferences.destination}\n"
            f"Trip duration: {preferences.duration} days\n"
            f"Travel style: {preferences.travel_style}\n"
            f"Group size: {preferences.group_size}\n"
            f"Interests: {', '.join(preferences.interests) if preferences.interests else 'General'}\n"
            f"Things to avoid: {', '.join(preferences.things_to_avoid) if preferences.things_to_avoid else 'None'}\n"
            f"Current weather: {trip.get('weather')}\n"
            f"Current budget: {trip.get('budget_breakdown')}\n"
            f"Existing day {day_number} context:\n{day_context}\n"
            f"Regenerate only day {day_number}. Preserve every other itinerary day exactly as-is."
        )
        system_prompt = (
            f"{ITINERARY_SYSTEM_PROMPT}\n\n"
            "You are regenerating exactly one itinerary day for an existing trip. "
            "Return a one-item itinerary list containing only the replacement for day_number "
            f"{day_number}. Do not regenerate or modify any other days."
        )

        response = invoke_with_fallback(
            lambda llm: build_structured_output(llm, ItineraryOutput),
            [SystemMessage(content=system_prompt), HumanMessage(content=content)],
        )
        if not getattr(response, "itinerary", None):
            raise DayRegenerationError("No itinerary day was generated.")
        generated_day = response.itinerary[0]
        generated_day.day_number = day_number
        return self._normalize_json_value(generated_day.model_dump(mode="json"))

    def trip_to_travelplan(self, trip: dict[str, Any]) -> TravelPlan:
        preferences = UserPreferences(
            destination=trip["destination"],
            duration=trip["duration"],
            total_budget=trip["total_budget"],
            budget_currency=trip["budget_currency"],
            travel_style=trip["travel_style"],
            interests=list(trip.get("interests") or []),
            things_to_avoid=list(trip.get("things_to_avoid") or []),
            group_size=trip["group_size"],
            travel_dates=trip.get("travel_dates"),
        )
        return TravelPlan(
            preferences=preferences,
            weather=WeatherInfo.model_validate(trip["weather"]) if trip.get("weather") else None,
            budget=BudgetBreakdown.model_validate(trip["budget_breakdown"]) if trip.get("budget_breakdown") else None,
            itinerary=[DayPlan.model_validate(day) for day in trip.get("itinerary") or []],
            critic_review=CriticReview.model_validate(trip["critic_review"]) if trip.get("critic_review") else None,
            revision_history=[RevisionRecord.model_validate(item) for item in trip.get("revision_history") or []],
            data_freshness=dict(trip.get("data_freshness") or {}),
            generated_at=self._ensure_utc_datetime(trip.get("updated_at") or trip.get("created_at")),
        )

    def _normalize_trip_input(
        self,
        travel_plan: TravelPlan | dict[str, Any] | None,
        trip_id: str | None,
    ) -> dict[str, Any]:
        if travel_plan is None:
            raise ValueError("A TravelPlan or trip document is required.")
        if isinstance(travel_plan, TravelPlan):
            return self.travelplan_to_trip(travel_plan, trip_id=trip_id)

        trip = self._normalize_json_value(dict(travel_plan))
        identifier = trip.get("id") or trip_id or str(uuid4())
        trip.update({
            "_id": identifier,
            "id": identifier,
            "is_group": bool(trip.get("is_group", False)),
            "created_at": self._ensure_utc_datetime(trip.get("created_at")),
            "updated_at": self._ensure_utc_datetime(trip.get("updated_at") or trip.get("created_at")),
        })
        for field in ("members", "invitations", "proposals", "decisions", "checklist_items"):
            trip.setdefault(field, [])
        return trip

    @staticmethod
    def _normalize_json_value(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: TripService._normalize_json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [TripService._normalize_json_value(item) for item in value]
        return value

    @staticmethod
    def _ensure_utc_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(UTC)
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def _next_timestamp(self) -> datetime:
        current = datetime.now(UTC)
        if self._last_timestamp is not None and current <= self._last_timestamp:
            current = self._last_timestamp + timedelta(microseconds=1)
        self._last_timestamp = current
        return current
