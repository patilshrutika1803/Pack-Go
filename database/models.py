from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index, text
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
    members: Mapped[list["TripMember"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    invitations: Mapped[list["TripInvitation"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    checklist_items: Mapped[list["ChecklistItem"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    messages: Mapped[list["GroupMessage"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="trip")


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
    trip_memberships: Mapped[list["TripMember"]] = relationship(back_populates="user", foreign_keys="TripMember.user_id")
    sent_invitations: Mapped[list["TripInvitation"]] = relationship(back_populates="inviter", foreign_keys="TripInvitation.inviter_user_id")
    proposals_created: Mapped[list["Proposal"]] = relationship(back_populates="creator", foreign_keys="Proposal.created_by_user_id")
    proposal_votes: Mapped[list["ProposalVote"]] = relationship(back_populates="voter")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="recipient", foreign_keys="Notification.recipient_user_id")
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


class TripMember(Base):
    __tablename__ = "trip_members"
    __table_args__ = (UniqueConstraint("trip_id", "user_id", name="uq_trip_member_user"), CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_trip_member_role"), CheckConstraint("status IN ('active', 'left', 'removed')", name="ck_trip_member_status"), Index("ix_trip_members_trip_status", "trip_id", "status"), Index("ix_trip_members_user_status", "user_id", "status"), Index("uq_trip_members_active_owner", "trip_id", unique=True, postgresql_where=text("status = 'active' AND role = 'owner'"), sqlite_where=text("status = 'active' AND role = 'owner'")))

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip: Mapped[Trip] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="trip_memberships", foreign_keys=[user_id])


class TripInvitation(Base):
    __tablename__ = "trip_invitations"
    __table_args__ = (CheckConstraint("status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')", name="ck_trip_invitation_status"), Index("ix_trip_invitations_trip_status", "trip_id", "status"), Index("ix_trip_invitations_invitee_user_status", "invitee_user_id", "status"), Index("ix_trip_invitations_expires_status", "expires_at", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    inviter_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    invitee_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    invitee_email: Mapped[str | None] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    trip: Mapped[Trip] = relationship(back_populates="invitations")
    inviter: Mapped[User] = relationship(back_populates="sent_invitations", foreign_keys=[inviter_user_id])


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (CheckConstraint("proposal_type IN ('destination', 'hotel', 'restaurant', 'activity', 'itinerary_item', 'other')", name="ck_proposal_type"), CheckConstraint("status IN ('draft', 'open', 'closed', 'accepted', 'rejected', 'cancelled')", name="ck_proposal_status"), Index("ix_proposals_trip_status_created", "trip_id", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip: Mapped[Trip] = relationship(back_populates="proposals")
    creator: Mapped[User] = relationship(back_populates="proposals_created", foreign_keys=[created_by_user_id])
    votes: Mapped[list["ProposalVote"]] = relationship(back_populates="proposal", cascade="all, delete-orphan")
    decision: Mapped["Decision | None"] = relationship(back_populates="proposal", uselist=False, viewonly=True)


class ProposalVote(Base):
    __tablename__ = "proposal_votes"
    __table_args__ = (UniqueConstraint("proposal_id", "user_id", name="uq_proposal_vote_user"), Index("ix_proposal_votes_choice", "proposal_id", "choice_key"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    choice_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    proposal: Mapped[Proposal] = relationship(back_populates="votes")
    voter: Mapped[User] = relationship(back_populates="proposal_votes")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("proposals.id", ondelete="CASCADE"), unique=True, nullable=False)
    decided_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(40), nullable=False)
    vote_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    proposal_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    applied_action: Mapped[dict | None] = mapped_column(JSON)
    source_revision: Mapped[int | None] = mapped_column(Integer)
    target_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    trip: Mapped[Trip] = relationship(back_populates="decisions")
    proposal: Mapped[Proposal] = relationship(back_populates="decision")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    __table_args__ = (Index("ix_checklist_trip_completed_due", "trip_id", "completed", "due_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    trip: Mapped[Trip] = relationship(back_populates="checklist_items")


class GroupMessage(Base):
    __tablename__ = "group_messages"
    __table_args__ = (Index("ix_group_messages_trip_created", "trip_id", "created_at", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    sender_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip: Mapped[Trip] = relationship(back_populates="messages")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_read_created", "recipient_user_id", "read_at", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    recipient_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trip_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trips.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    recipient: Mapped[User] = relationship(back_populates="notifications", foreign_keys=[recipient_user_id])
    trip: Mapped[Trip | None] = relationship(back_populates="notifications")