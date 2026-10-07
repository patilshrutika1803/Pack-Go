from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database
from pymongo.errors import PyMongoError

from api.v1.dependencies import CurrentUser, get_current_admin
from database.mongodb import get_database

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class UnavailableMetric(BaseModel):
    available: bool = False
    reason: str


class DestinationMetric(BaseModel):
    destination: str
    trip_count: int = Field(ge=0)


class AdminAnalytics(BaseModel):
    total_users: int = Field(ge=0)
    total_trips: int = Field(ge=0)
    group_trips: int = Field(ge=0)
    destinations: list[DestinationMetric]
    expense_count: int = Field(ge=0)
    expense_total: float = Field(ge=0)
    journal_entry_count: int = Field(ge=0)
    active_users: UnavailableMetric
    ai_requests: UnavailableMetric
    agent_usage: UnavailableMetric
    provider_usage: UnavailableMetric


class KnowledgeStatus(BaseModel):
    total_sources: int = Field(ge=0)
    indexed_sources: int = Field(ge=0)
    processing_sources: int = Field(ge=0)
    failed_sources: int = Field(ge=0)


class SystemStatus(BaseModel):
    database: str
    knowledge: KnowledgeStatus


class AdminOverview(BaseModel):
    analytics: AdminAnalytics
    system: SystemStatus


def _unavailable(reason: str) -> UnavailableMetric:
    return UnavailableMetric(reason=reason)


@router.get("/overview", response_model=AdminOverview)
def get_admin_overview(
    db: Database = Depends(get_database),
    _: CurrentUser = Depends(get_current_admin),
) -> AdminOverview:
    try:
        total_users = db.users.count_documents({})
        total_trips = db.trips.count_documents({})
        group_trips = db.trips.count_documents({"is_group": True})
        destination_rows = list(db.trips.aggregate([
            {"$group": {"_id": "$destination", "trip_count": {"$sum": 1}}},
            {"$sort": {"trip_count": -1, "_id": 1}},
        ]))
        expense_count = db.expenses.count_documents({})
        expense_total = sum(
            (item["amount"].to_decimal() if hasattr(item["amount"], "to_decimal") else Decimal(str(item["amount"]))
             for item in db.expenses.find({}, {"amount": 1})),
            start=Decimal("0"),
        )
        journal_entry_count = db.journal_entries.count_documents({})
        source_counts = {
            status: db.knowledge_sources.count_documents({"status": status})
            for status in ("indexed", "processing", "failed")
        }
        total_sources = db.knowledge_sources.count_documents({})
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Administrative status is temporarily unavailable.") from exc

    unavailable_reason = "No persisted activity or request telemetry is recorded by the current application."
    return AdminOverview(
        analytics=AdminAnalytics(
            total_users=total_users,
            total_trips=total_trips,
            group_trips=group_trips,
            destinations=[
                DestinationMetric(destination=row["_id"], trip_count=row["trip_count"])
                for row in destination_rows
            ],
            expense_count=expense_count,
            expense_total=float(expense_total),
            journal_entry_count=journal_entry_count,
            active_users=_unavailable("No reliable user activity timestamp or event source exists."),
            ai_requests=_unavailable(unavailable_reason),
            agent_usage=_unavailable(unavailable_reason),
            provider_usage=_unavailable("Provider quota and request usage are not persisted by the current integrations."),
        ),
        system=SystemStatus(
            database="healthy",
            knowledge=KnowledgeStatus(
                total_sources=total_sources,
                indexed_sources=source_counts["indexed"],
                processing_sources=source_counts["processing"],
                failed_sources=source_counts["failed"],
            ),
        ),
    )
