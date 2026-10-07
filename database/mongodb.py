from __future__ import annotations

import os
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

load_dotenv()

_client: MongoClient[dict[str, Any]] | None = None
_database: Database[dict[str, Any]] | None = None
_lock = Lock()


def get_database() -> Database[dict[str, Any]]:
    global _client, _database
    if _database is not None:
        return _database

    with _lock:
        if _database is not None:
            return _database
        uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MONGODB_DATABASE")
        if not uri:
            raise RuntimeError("MONGODB_URI must be configured.")
        if not database_name:
            raise RuntimeError("MONGODB_DATABASE must be configured.")

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        database = client[database_name]
        _create_indexes(database)
        _client = client
        _database = database
        return database


def _create_indexes(database: Database[dict[str, Any]]) -> None:
    database.users.create_index("email", unique=True, sparse=True)
    database.trips.create_index("user_id")
    database.trips.create_index("members.user_id")
    database.trip_messages.create_index([("trip_id", 1), ("created_at", -1), ("_id", -1)])
    database.notifications.create_index([("recipient_user_id", 1), ("created_at", -1)])
    database.expenses.create_index([("trip_id", 1), ("expense_date", -1), ("created_at", -1)])
    database.journal_entries.create_index([("trip_id", 1), ("occurred_at", 1), ("_id", 1)])
    database.knowledge_sources.create_index("document_id", unique=True)
    database.knowledge_sources.create_index([("created_at", -1)])


def close_database() -> None:
    global _client, _database
    with _lock:
        if _client is not None:
            _client.close()
        _client = None
        _database = None
