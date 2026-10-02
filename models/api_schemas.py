from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TripCreateRequest(BaseModel):
    id: str | None = None
    title: str
    destination: str
    duration: int
    total_budget: float
    budget_currency: str = "INR"
    group_size: int = 1
    travel_style: str = "balanced"
    travel_dates: str | None = None
    interests: list[str] = Field(default_factory=list)
    things_to_avoid: list[str] = Field(default_factory=list)
    itinerary: list[dict[str, Any]] = Field(default_factory=list)
    weather: dict[str, Any] | None = None
    budget_breakdown: dict[str, Any] | None = None
    critic_review: dict[str, Any] | None = None
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    data_freshness: dict[str, Any] = Field(default_factory=dict)
    original_query: str | None = None


class TripUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    destination: str | None = None
    duration: int | None = None
    total_budget: float | None = None
    budget_currency: str | None = None
    group_size: int | None = None
    travel_style: str | None = None
    travel_dates: str | None = None
    interests: list[str] | None = None
    things_to_avoid: list[str] | None = None
    itinerary: list[dict[str, Any]] | None = None
    weather: dict[str, Any] | None = None
    budget_breakdown: dict[str, Any] | None = None
    critic_review: dict[str, Any] | None = None
    revision_history: list[dict[str, Any]] | None = None
    data_freshness: dict[str, Any] | None = None
    original_query: str | None = None


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    destination: str
    duration: int
    total_budget: float
    budget_currency: str
    group_size: int
    travel_style: str
    travel_dates: str | None = None
    interests: list[str] = Field(default_factory=list)
    things_to_avoid: list[str] = Field(default_factory=list)
    itinerary: list[dict[str, Any]] = Field(default_factory=list)
    weather: dict[str, Any] | None = None
    budget_breakdown: dict[str, Any] | None = None
    critic_review: dict[str, Any] | None = None
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    data_freshness: dict[str, Any] = Field(default_factory=dict)
    original_query: str | None = None
    created_at: datetime
    updated_at: datetime


class TripDayRegenerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: str
    day_number: int
    regenerated_day: dict[str, Any]
    updated_at: datetime


class RouteOptimizationRequest(BaseModel):
    start_location_id: str | None = Field(default=None, min_length=1, max_length=100)
    goal_location_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_location_pair(self):
        if (self.start_location_id is None) != (self.goal_location_id is None):
            raise ValueError("Provide both a start location and a destination.")
        if self.start_location_id is not None and self.start_location_id == self.goal_location_id:
            raise ValueError("Start location and destination must be different.")
        return self


class ItineraryCSPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItineraryGARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    population_size: int = Field(default=20, ge=4, le=100)
    generations: int = Field(default=20, ge=1, le=100)
    mutation_rate: float = Field(default=0.1, ge=0, le=1)
    random_seed: int | None = Field(default=None, ge=0, le=4_294_967_295)


class DeleteTripResponse(BaseModel):
    message: str


ExpenseCategory = Literal["accommodation", "food", "transport", "activities", "shopping", "other"]
ExpenseSplitType = Literal["equal", "custom"]


class ExpenseParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=36)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class ExpenseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payer_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    category: ExpenseCategory
    expense_date: date = Field(default_factory=date.today)
    description: str | None = Field(default=None, max_length=2000)
    split_type: ExpenseSplitType = "equal"
    participants: list[ExpenseParticipantInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_participants(self):
        _validate_expense_split(self.amount, self.split_type, self.participants)
        return self


class ExpenseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    payer_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    category: ExpenseCategory | None = None
    expense_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    split_type: ExpenseSplitType | None = None
    participants: list[ExpenseParticipantInput] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_requested_split(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if self.participants is not None:
            _validate_unique_expense_participants(self.participants)
            if self.split_type == "equal" and any(item.amount is not None for item in self.participants):
                raise ValueError("Equal split participants must not include amounts.")
            if self.split_type == "custom" and any(item.amount is None for item in self.participants):
                raise ValueError("Custom split participants must include an amount.")
        return self


def _validate_unique_expense_participants(participants: list[ExpenseParticipantInput]) -> None:
    ids = [participant.user_id for participant in participants]
    if len(ids) != len(set(ids)):
        raise ValueError("Expense participants must be unique.")


def _validate_expense_split(amount: Decimal, split_type: ExpenseSplitType, participants: list[ExpenseParticipantInput]) -> None:
    _validate_unique_expense_participants(participants)
    if split_type == "equal" and any(item.amount is not None for item in participants):
        raise ValueError("Equal split participants must not include amounts.")
    if split_type == "custom":
        if any(item.amount is None for item in participants):
            raise ValueError("Custom split participants must include an amount.")
        if sum((item.amount for item in participants), Decimal("0")) != amount:
            raise ValueError("Custom participant shares must equal the expense amount.")


class ExpenseParticipantResponse(BaseModel):
    user_id: str
    name: str
    amount: Decimal


class ExpenseResponse(BaseModel):
    id: str
    trip_id: str
    created_by_user_id: str
    payer_user_id: str
    payer_name: str
    amount: Decimal
    category: ExpenseCategory
    expense_date: date
    description: str | None
    split_type: ExpenseSplitType
    participants: list[ExpenseParticipantResponse]
    created_at: datetime
    updated_at: datetime


class ExpenseParticipantBalance(BaseModel):
    user_id: str
    name: str
    total_paid: Decimal
    total_owed: Decimal
    balance: Decimal


class ExpenseSettlement(BaseModel):
    from_user_id: str
    from_name: str
    to_user_id: str
    to_name: str
    amount: Decimal


class ExpenseSummaryResponse(BaseModel):
    trip_id: str
    expense_count: int
    total_expenses: Decimal
    category_totals: dict[str, Decimal]
    date_totals: dict[str, Decimal]
    participants: list[ExpenseParticipantBalance]
    settlements: list[ExpenseSettlement]


class JournalEntryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    occurred_at: datetime | None = None
    media_references: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_journal_content_and_media(self):
        from urllib.parse import urlsplit

        self.content = self.content.strip()
        if not self.content:
            raise ValueError("Journal content must not be empty.")
        if self.title is not None:
            self.title = self.title.strip() or None
        for reference in self.media_references:
            parsed = urlsplit(reference.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Media references must be absolute HTTP or HTTPS URLs.")
        self.media_references = [reference.strip() for reference in self.media_references]
        return self


class JournalEntryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    occurred_at: datetime | None = None
    media_references: list[str] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def validate_requested_fields(self):
        from urllib.parse import urlsplit

        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "content" in self.model_fields_set and self.content is None:
            raise ValueError("Journal content must not be empty.")
        if "occurred_at" in self.model_fields_set and self.occurred_at is None:
            raise ValueError("Journal date and time must not be empty.")
        if "media_references" in self.model_fields_set and self.media_references is None:
            raise ValueError("Media references must be a list.")
        if self.content is not None:
            self.content = self.content.strip()
            if not self.content:
                raise ValueError("Journal content must not be empty.")
        if self.title is not None:
            self.title = self.title.strip() or None
        if self.media_references is not None:
            for reference in self.media_references:
                parsed = urlsplit(reference.strip())
                if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError("Media references must be absolute HTTP or HTTPS URLs.")
            self.media_references = [reference.strip() for reference in self.media_references]
        return self


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    created_by_user_id: str
    author_name: str
    title: str | None
    content: str
    occurred_at: datetime
    media_references: list[str]
    created_at: datetime
    updated_at: datetime


class TripJournalStatisticsResponse(BaseModel):
    trip_id: str
    planned_duration_days: int
    journal_entry_count: int
    journal_days_covered: int
    media_reference_count: int
    expense_total: Decimal
    expense_currency: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    is_active: bool
    is_verified: bool
    is_admin: bool = False


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    verification_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class PreferenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    travel_style: Literal["Relaxation", "Balanced", "Adventure", "Luxury", "Budget"] | None = None
    interests: list[Literal["Beach", "Food", "Culture", "Nature", "Adventure", "Wellness", "Nightlife"]] | None = None
    things_to_avoid: list[str] | None = None
    budget_preference: Literal["Budget", "Moderate", "Luxury", "Flexible"] | None = None
    hotel_preference: Literal["Budget", "Mid-range", "Luxury", "Boutique", "Hostel"] | None = None
    food_preference: Literal["Local", "Vegetarian", "Street food", "Fine dining", "Anything"] | None = None
    preferred_destinations: list[str] | None = None
    preferred_budget_min: float | None = Field(default=None, ge=0)
    preferred_budget_max: float | None = Field(default=None, ge=0)
    preferred_currency: str | None = None
    preferred_trip_duration: int | None = Field(default=None, ge=1, le=365)
    is_domestic: bool | None = None

    @model_validator(mode="after")
    def validate_budget_range(self):
        if self.preferred_budget_min is not None and self.preferred_budget_max is not None and self.preferred_budget_min > self.preferred_budget_max:
            raise ValueError("preferred_budget_min must not exceed preferred_budget_max")
        return self


class PreferenceResponse(PreferenceUpdateRequest):
    model_config = ConfigDict(from_attributes=True)

    travel_style: str | None = None
    interests: list[str] | None = None
    budget_preference: str | None = None
    hotel_preference: str | None = None
    food_preference: str | None = None
    id: str
    user_id: str


class TripGroupCreateRequest(BaseModel):
    pass


class TripMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    user_id: str
    role: Literal["owner", "admin", "member"]
    status: Literal["active", "left", "removed"]
    joined_at: datetime
    left_at: datetime | None = None
    removed_at: datetime | None = None
    user: UserResponse | None = None


class TripMemberRoleUpdateRequest(BaseModel):
    role: Literal["admin", "member"]


class OwnershipTransferRequest(BaseModel):
    target_user_id: str = Field(min_length=1, max_length=36)


class TripMemberListResponse(BaseModel):
    members: list[TripMemberResponse]


class WorkspaceResponse(BaseModel):
    trip_id: str
    is_group: bool
    member_count: int
    members: list[TripMemberResponse]


class InvitationCreateRequest(BaseModel):
    invitee_user_id: str | None = None
    invitee_email: str | None = Field(default=None, min_length=3, max_length=320)
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def target_required(self):
        if self.invitee_user_id and self.invitee_email:
            raise ValueError("Provide at most one invitation target.")
        return self


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    invitee_user_id: str | None = None
    invitee_email: str | None = None
    status: str
    expires_at: datetime
    created_at: datetime
    token: str | None = None


class InvitationAcceptResponse(BaseModel):
    invitation_id: str
    trip_id: str
    membership: TripMemberResponse


class InvitationPreviewResponse(BaseModel):
    trip_id: str
    trip_title: str
    destination: str
    duration: int
    member_count: int
    expires_at: datetime
    status: str


ProposalType = Literal["destination", "hotel", "restaurant", "activity", "itinerary_item", "other"]


class ProposalCreateRequest(BaseModel):
    proposal_type: ProposalType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    payload: dict[str, Any]
    deadline: datetime | None = None

    @model_validator(mode="after")
    def validate_payload_for_type(self):
        required = {
            "destination": ("destination",),
            "hotel": ("name",),
            "restaurant": ("name",),
            "activity": ("name",),
            "itinerary_item": ("day_number", "value"),
        }.get(self.proposal_type, ())
        missing = [field for field in required if field not in self.payload or self.payload[field] in (None, "")]
        if missing:
            raise ValueError(f"Payload for {self.proposal_type} requires: {', '.join(missing)}.")
        if self.proposal_type == "itinerary_item" and (not isinstance(self.payload["day_number"], int) or self.payload["day_number"] < 1):
            raise ValueError("itinerary_item day_number must be a positive integer.")
        return self


class ProposalUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    payload: dict[str, Any] | None = None
    deadline: datetime | None = None


class ProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    created_by_user_id: str
    proposal_type: str
    title: str
    description: str | None
    payload: dict[str, Any]
    status: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    vote_count: int = 0


class ProposalListResponse(BaseModel):
    proposals: list[ProposalResponse]


class VoteRequest(BaseModel):
    choice_key: str = Field(min_length=1, max_length=120)


class VoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    proposal_id: str
    user_id: str
    choice_key: str
    created_at: datetime
    updated_at: datetime


class ProposalResultResponse(BaseModel):
    proposal_id: str
    status: str
    counts: dict[str, int]
    winner: str | None
    ties: list[str] = []
    user_vote: str | None = None
    decision: "DecisionResponse | None" = None


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    proposal_id: str
    decided_by_user_id: str
    result: str
    decision_type: str
    vote_counts: dict[str, int]
    proposal_snapshot: dict[str, Any]
    applied_action: dict[str, Any] | None
    source_revision: int | None
    target_revision: int | None
    created_at: datetime


class DecisionApplyResponse(BaseModel):
    decision: DecisionResponse
    applied: bool


class ChecklistItemCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to_user_id: str | None = None
    due_at: datetime | None = None


class ChecklistItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to_user_id: str | None = None
    due_at: datetime | None = None
    completed: bool | None = None

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one checklist field is required.")
        return self


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    created_by_user_id: str
    assigned_to_user_id: str | None
    title: str
    description: str | None
    completed: bool
    completed_by_user_id: str | None
    completed_at: datetime | None
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def body_not_blank(self):
        if not self.body.strip():
            raise ValueError("Message cannot be blank.")
        return self


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trip_id: str
    sender_user_id: str
    sender_name: str | None = None
    body: str
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None


class MessagePageResponse(BaseModel):
    messages: list[MessageResponse]
    next_cursor: str | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recipient_user_id: str
    trip_id: str | None
    event_type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
