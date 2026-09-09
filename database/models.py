from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Trip(Base):
    """
    Persistent representation of a PACK & GO trip.

    The generated itinerary and AI metadata are stored as JSON so that
    the existing Pydantic TravelPlan structure does not need to be changed.
    """

    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    destination: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_budget: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    budget_currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="INR",
    )

    group_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    travel_style: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="balanced",
    )

    travel_dates: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    interests: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    things_to_avoid: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    itinerary: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    weather: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    budget_breakdown: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    critic_review: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    revision_history: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    data_freshness: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    original_query: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class User(Base):
    """Account identity and password credentials for authenticated features."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))