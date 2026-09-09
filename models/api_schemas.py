from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
