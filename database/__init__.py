from __future__ import annotations

from importlib import import_module
from typing import Any

_LEGACY_SQL_EXPORTS = {
    "Base": ("database.base", "Base"),
    "SessionLocal": ("database.connection", "SessionLocal"),
    "engine": ("database.connection", "engine"),
    "get_db": ("database.connection", "get_db"),
    **{
        name: ("database.models", name)
        for name in (
            "Trip", "User", "UserPreference", "RefreshToken", "VerificationToken",
            "PasswordResetToken", "KnowledgeSource", "TripMember", "TripInvitation",
            "Proposal", "ProposalVote", "Decision", "ChecklistItem", "GroupMessage",
            "Notification", "Expense", "ExpenseShare", "JournalEntry",
        )
    },
}

__all__ = list(_LEGACY_SQL_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _LEGACY_SQL_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, symbol_name = target
    return getattr(import_module(module_name), symbol_name)
