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
