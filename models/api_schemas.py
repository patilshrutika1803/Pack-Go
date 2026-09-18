from __future__ import annotations

from datetime import datetime
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


class DeleteTripResponse(BaseModel):
    message: str


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
