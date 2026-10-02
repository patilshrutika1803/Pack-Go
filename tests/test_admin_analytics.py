import importlib
from datetime import UTC, datetime, date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from database import Expense, JournalEntry, KnowledgeSource, Trip, User
from tests.test_authentication import auth_header, register


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    db_file = tmp_path / "admin.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")
    import database.connection as connection_module
    import database as database_module
    connection_module = importlib.reload(connection_module)
    importlib.reload(database_module)
    from database.base import Base
    Base.metadata.create_all(bind=connection_module.engine)
    import main as main_module
    main_module = importlib.reload(main_module)
    import api.v1.dependencies as dependency_module
    main_module.app.dependency_overrides[dependency_module.get_db] = connection_module.get_db
    return TestClient(main_module.app, raise_server_exceptions=False)


def _make_admin(payload):
    from database.connection import SessionLocal

    with SessionLocal() as db:
        user = db.get(User, payload["user"]["id"])
        user.is_admin = True
        db.commit()


def test_admin_overview_requires_admin(admin_client):
    assert admin_client.get("/api/v1/admin/overview").status_code == 401
    user = register(admin_client, "analytics-user@example.com")
    assert admin_client.get("/api/v1/admin/overview", headers=auth_header(user)).status_code == 403


def test_admin_overview_reports_supported_aggregates_without_private_content(admin_client):
    admin = register(admin_client, "analytics-admin@example.com")
    _make_admin(admin)
    other = register(admin_client, "analytics-other@example.com")
    trip_id = str(uuid4())
    with __import__("database.connection", fromlist=["SessionLocal"]).SessionLocal() as db:
        db.add_all([
            Trip(id=trip_id, user_id=other["user"]["id"], is_group=True, title="Group trip", destination="Goa", duration=3, total_budget=500, budget_currency="INR", group_size=2, travel_style="balanced", interests=[], things_to_avoid=[], itinerary=[], revision_history=[], data_freshness={}),
            Trip(id=str(uuid4()), user_id=other["user"]["id"], title="Solo trip", destination="Goa", duration=2, total_budget=300, budget_currency="INR", group_size=1, travel_style="balanced", interests=[], things_to_avoid=[], itinerary=[], revision_history=[], data_freshness={}),
            Expense(id=str(uuid4()), trip_id=trip_id, created_by_user_id=other["user"]["id"], payer_user_id=other["user"]["id"], amount=Decimal("125.50"), category="food", expense_date=date(2026, 10, 1), description="Private expense", split_type="equal"),
            JournalEntry(id=str(uuid4()), trip_id=trip_id, created_by_user_id=other["user"]["id"], title="Private note", content="Private journal content", occurred_at=datetime.now(UTC), media_references=[]),
            KnowledgeSource(id=str(uuid4()), document_id="analytics-doc", filename="guide.pdf", display_name="Guide", destination="Goa", category="guide", document_type="pdf", file_path="/private/guide.pdf", chunk_count=1, page_count=1, status="indexed"),
        ])
        db.commit()

    response = admin_client.get("/api/v1/admin/overview", headers=auth_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["analytics"]["total_users"] == 2
    assert body["analytics"]["total_trips"] == 2
    assert body["analytics"]["group_trips"] == 1
    assert body["analytics"]["destinations"] == [{"destination": "Goa", "trip_count": 2}]
    assert body["analytics"]["expense_count"] == 1
    assert body["analytics"]["expense_total"] == 125.5
    assert body["analytics"]["journal_entry_count"] == 1
    assert body["system"]["knowledge"] == {"total_sources": 1, "indexed_sources": 1, "processing_sources": 0, "failed_sources": 0}
    assert body["analytics"]["active_users"]["available"] is False
    assert body["analytics"]["ai_requests"]["available"] is False
    assert "Private" not in response.text
    assert "file_path" not in response.text


def test_admin_overview_empty_data_is_deterministic(admin_client):
    admin = register(admin_client, "empty-admin@example.com")
    _make_admin(admin)

    body = admin_client.get("/api/v1/admin/overview", headers=auth_header(admin)).json()

    assert body["analytics"]["total_users"] == 1
    assert body["analytics"]["total_trips"] == 0
    assert body["analytics"]["destinations"] == []
    assert body["analytics"]["expense_total"] == 0
    assert body["system"]["knowledge"]["total_sources"] == 0