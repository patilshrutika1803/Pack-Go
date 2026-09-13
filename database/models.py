from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
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

    owner: Mapped["User | None"] = relationship(back_populates="trips")


class User(Base):
    """Account identity and password credentials for authenticated features."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    trips: Mapped[list[Trip]] = relationship(back_populates="owner")
    preferences: Mapped["UserPreference | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    travel_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    things_to_avoid: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    budget_preference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hotel_preference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    food_preference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_destinations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preferred_budget_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_budget_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    preferred_trip_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_domestic: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user: Mapped[User] = relationship(back_populates="preferences")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class KnowledgeSource(Base):
    """Relational source-of-truth for indexed travel documents."""

    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="indexed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))