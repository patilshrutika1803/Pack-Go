from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from database.models import Expense, JournalEntry
from services.collaboration_service import AccessDenied, TripAccessService


class JournalService:
    def __init__(self, db: Session):
        self.db = db
        self.access = TripAccessService(db)

    def list_entries(self, trip_id: str, user_id: str) -> list[JournalEntry]:
        self.access.get_trip_for_member(trip_id, user_id)
        return list(self.db.scalars(
            select(JournalEntry)
            .options(selectinload(JournalEntry.author))
            .where(JournalEntry.trip_id == trip_id)
            .order_by(JournalEntry.occurred_at, JournalEntry.id)
        ).all())

    def create(self, trip_id: str, user_id: str, data: dict) -> JournalEntry:
        self.access.get_trip_for_member(trip_id, user_id)
        payload = dict(data)
        payload["title"] = payload.get("title")
        payload["content"] = payload["content"].strip()
        if not payload["content"]:
            raise ValueError("Journal content must not be empty.")
        entry = JournalEntry(
            id=str(uuid4()),
            trip_id=trip_id,
            created_by_user_id=user_id,
            occurred_at=payload.get("occurred_at") or datetime.now(UTC),
            media_references=payload.get("media_references") or [],
            title=payload["title"],
            content=payload["content"],
        )
        return self._save(entry, "create")

    def update(self, entry_id: str, user_id: str, updates: dict) -> JournalEntry:
        entry = self._get_authorized_entry(entry_id, user_id)
        if entry.created_by_user_id != user_id:
            raise AccessDenied("Journal entry cannot be edited.")
        for key, value in updates.items():
            if key == "content":
                value = value.strip()
                if not value:
                    raise ValueError("Journal content must not be empty.")
            if key == "title" and value is not None:
                value = value.strip() or None
            setattr(entry, key, value)
        entry.updated_at = datetime.now(UTC)
        return self._save(entry, "update")

    def delete(self, entry_id: str, user_id: str) -> None:
        entry = self._get_authorized_entry(entry_id, user_id)
        if entry.created_by_user_id != user_id:
            raise AccessDenied("Journal entry cannot be deleted.")
        self.db.delete(entry)
        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise RuntimeError("Failed to delete journal entry.") from exc

    def statistics(self, trip_id: str, user_id: str) -> dict:
        trip = self.access.get_trip_for_member(trip_id, user_id)
        entries = list(self.db.scalars(select(JournalEntry).where(JournalEntry.trip_id == trip_id)).all())
        expense_total = self.db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.trip_id == trip_id)
        )
        return {
            "trip_id": trip_id,
            "planned_duration_days": trip.duration,
            "journal_entry_count": len(entries),
            "journal_days_covered": len({entry.occurred_at.date() for entry in entries}),
            "media_reference_count": sum(len(entry.media_references or []) for entry in entries),
            "expense_total": expense_total,
            "expense_currency": trip.budget_currency,
        }

    def _get_authorized_entry(self, entry_id: str, user_id: str) -> JournalEntry:
        entry = self.db.get(JournalEntry, entry_id)
        if entry is None:
            raise AccessDenied("Journal entry not found.")
        self.access.get_trip_for_member(entry.trip_id, user_id)
        return entry

    def _save(self, entry: JournalEntry, action: str) -> JournalEntry:
        try:
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)
            return entry
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise RuntimeError(f"Failed to {action} journal entry.") from exc