from __future__ import annotations

import os
from datetime import UTC, datetime

from database.mongodb import get_database


def main() -> None:
    user_id = os.getenv("SUPABASE_USER_ID", "").strip()
    if not user_id:
        raise RuntimeError("Set SUPABASE_USER_ID to the existing Supabase Auth UUID to grant admin access.")

    now = datetime.now(UTC)
    database = get_database()
    database.users.update_one(
        {"_id": user_id},
        {
            "$set": {"id": user_id, "supabase_user_id": user_id, "is_admin": True, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    print(f"Granted admin access to Supabase user {user_id}.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
