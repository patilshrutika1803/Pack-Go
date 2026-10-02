from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.v1.dependencies import get_current_admin
from database import Expense, JournalEntry, KnowledgeSource, Trip, User
from database.connection import get_db


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
def get_admin_overview(db: Session = Depends(get_db), _: User = Depends(get_current_admin)) -> AdminOverview:
    try:
        db.execute(text("SELECT 1"))
        total_users = db.scalar(select(func.count(User.id))) or 0
        total_trips = db.scalar(select(func.count(Trip.id))) or 0
        group_trips = db.scalar(select(func.count(Trip.id)).where(Trip.is_group.is_(True))) or 0
        destination_rows = db.execute(
            select(Trip.destination, func.count(Trip.id))
            .group_by(Trip.destination)
            .order_by(func.count(Trip.id).desc(), Trip.destination.asc())
        ).all()
        expense_count = db.scalar(select(func.count(Expense.id))) or 0
        expense_total = db.scalar(select(func.sum(Expense.amount))) or Decimal("0")
        journal_entry_count = db.scalar(select(func.count(JournalEntry.id))) or 0
        total_sources = db.scalar(select(func.count(KnowledgeSource.id))) or 0
        indexed_sources = db.scalar(select(func.count(KnowledgeSource.id)).where(KnowledgeSource.status == "indexed")) or 0
        processing_sources = db.scalar(select(func.count(KnowledgeSource.id)).where(KnowledgeSource.status == "processing")) or 0
        failed_sources = db.scalar(select(func.count(KnowledgeSource.id)).where(KnowledgeSource.status == "failed")) or 0
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Administrative status is temporarily unavailable.") from exc

    unavailable_reason = "No persisted activity or request telemetry is recorded by the current application."
    return AdminOverview(
        analytics=AdminAnalytics(
            total_users=total_users,
            total_trips=total_trips,
            group_trips=group_trips,
            destinations=[DestinationMetric(destination=destination, trip_count=count) for destination, count in destination_rows],
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
                indexed_sources=indexed_sources,
                processing_sources=processing_sources,
                failed_sources=failed_sources,
            ),
        ),
    )