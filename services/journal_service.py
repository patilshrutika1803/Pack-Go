from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pymongo.database import Database

from services.collaboration_service import AccessDenied, TripAccessService


class JournalService:
    def __init__(self, database: Database):
        self.database = database
        self.access = TripAccessService(database)

    def list_entries(self, trip_id: str, user_id: str) -> list[dict]:
        self.access.get_trip_for_member(trip_id, user_id)
        entries = self.database.journal_entries.find({"trip_id": trip_id}).sort(
            [("occurred_at", 1), ("_id", 1)]
        )
        return [self._with_author(entry) for entry in entries]

    def create(self, trip_id: str, user_id: str, data: dict) -> dict:
        self.access.get_trip_for_member(trip_id, user_id)
        content = data["content"].strip()
        if not content:
            raise ValueError("Journal content must not be empty.")
        now = datetime.now(UTC)
        entry_id = str(uuid4())
        entry = {
            "_id": entry_id,
            "id": entry_id,
            "trip_id": trip_id,
            "created_by_user_id": user_id,
            "occurred_at": data.get("occurred_at") or now,
            "media_references": data.get("media_references") or [],
            "title": data.get("title"),
            "content": content,
            "created_at": now,
            "updated_at": now,
        }
        self.database.journal_entries.insert_one(entry)
        return self._with_author(entry)

    def update(self, entry_id: str, user_id: str, updates: dict) -> dict:
        entry = self._get_authorized_entry(entry_id, user_id)
        if entry["created_by_user_id"] != user_id:
            raise AccessDenied("Journal entry cannot be edited.")
        for key, value in updates.items():
            if key == "content":
                value = value.strip()
                if not value:
                    raise ValueError("Journal content must not be empty.")
            if key == "title" and value is not None:
                value = value.strip() or None
            entry[key] = value
        entry["updated_at"] = datetime.now(UTC)
        self.database.journal_entries.update_one({"_id": entry_id}, {"$set": {
            key: entry[key] for key in updates
        } | {"updated_at": entry["updated_at"]}})
        return self._with_author(entry)

    def delete(self, entry_id: str, user_id: str) -> None:
        entry = self._get_authorized_entry(entry_id, user_id)
        if entry["created_by_user_id"] != user_id:
            raise AccessDenied("Journal entry cannot be deleted.")
        self.database.journal_entries.delete_one({"_id": entry_id})

    def statistics(self, trip_id: str, user_id: str) -> dict:
        trip = self.access.get_trip_for_member(trip_id, user_id)
        entries = list(self.database.journal_entries.find({"trip_id": trip_id}))
        expense_total = sum(
            (self._decimal_amount(expense["amount"]) for expense in self.database.expenses.find({"trip_id": trip_id})),
            start=self._zero(),
        )
        return {
            "trip_id": trip_id,
            "planned_duration_days": trip["duration"],
            "journal_entry_count": len(entries),
            "journal_days_covered": len({
                entry["occurred_at"].date() for entry in entries
            }),
            "media_reference_count": sum(len(entry.get("media_references") or []) for entry in entries),
            "expense_total": expense_total,
            "expense_currency": trip["budget_currency"],
        }

    def _get_authorized_entry(self, entry_id: str, user_id: str) -> dict:
        entry = self.database.journal_entries.find_one({"_id": entry_id})
        if entry is None:
            raise AccessDenied("Journal entry not found.")
        self.access.get_trip_for_member(entry["trip_id"], user_id)
        return entry

    def _with_author(self, entry: dict) -> dict:
        author = self.database.users.find_one(
            {"_id": entry["created_by_user_id"]}, {"name": 1}
        )
        return {**entry, "author_name": author["name"] if author else entry["created_by_user_id"]}

    @staticmethod
    def _decimal_amount(value):
        if hasattr(value, "to_decimal"):
            return value.to_decimal()
        from decimal import Decimal
        return Decimal(str(value))

    @staticmethod
    def _zero():
        from decimal import Decimal
        return Decimal("0.00")
