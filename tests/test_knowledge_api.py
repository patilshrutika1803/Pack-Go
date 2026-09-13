from pathlib import Path
import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from database import KnowledgeSource, User
from tests.test_authentication import auth_header, register


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    db_file = tmp_path / "knowledge.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")
    import database.connection as connection_module
    import database as database_module
    connection_module = importlib.reload(connection_module)
    importlib.reload(database_module)
    from database.base import Base
    Base.metadata.create_all(bind=connection_module.engine)
    if "is_admin" not in {column["name"] for column in inspect(connection_module.engine).get_columns("users")}:
        with connection_module.engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
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


def test_knowledge_endpoints_require_authentication_and_admin(auth_client):
    assert auth_client.get("/api/v1/admin/knowledge/documents").status_code == 401
    user = register(auth_client, "knowledge-user@example.com")
    assert auth_client.get("/api/v1/admin/knowledge/documents", headers=auth_header(user)).status_code == 403


def test_admin_upload_validates_filename_and_pdf(auth_client):
    user = register(auth_client, "knowledge-admin@example.com")
    _make_admin(user)
    headers = auth_header(user)
    fields = {
        "display_name": "Goa Guide",
        "destination": "Goa",
        "category": "travel_guide",
        "document_type": "destination_guide",
    }

    invalid_type = auth_client.post(
        "/api/v1/admin/knowledge/documents",
        headers=headers,
        files={"file": ("guide.txt", b"%PDF-invalid", "application/pdf")},
        data=fields,
    )
    assert invalid_type.status_code == 422

    traversal = auth_client.post(
        "/api/v1/admin/knowledge/documents",
        headers=headers,
        files={"file": ("../guide.pdf", b"%PDF-invalid", "application/pdf")},
        data=fields,
    )
    assert traversal.status_code == 422


def test_admin_upload_list_detail_delete_isolates_document_chunks(auth_client, monkeypatch, tmp_path):
    user = register(auth_client, "knowledge-owner@example.com")
    _make_admin(user)
    stored_path = tmp_path / "stored.pdf"
    stored_path.write_bytes(b"%PDF-test")

    def fake_ingest(path, destination, category, document_type, db, display_name, **kwargs):
        source = KnowledgeSource(
            id="source-1", document_id="document-1", filename=Path(path).name,
            display_name=display_name, destination=destination, category=category,
            document_type=document_type, file_path=str(stored_path), chunk_count=2,
            page_count=1, status="indexed",
        )
        db.add(source)
        db.commit()
        return {"document_id": "document-1"}

    monkeypatch.setattr("api.v1.knowledge.ingest_pdf", fake_ingest)
    deleted = []
    monkeypatch.setattr(
        "api.v1.knowledge.get_knowledge_collection",
        lambda: type("Collection", (), {"delete": lambda self, **kwargs: deleted.append(kwargs)})(),
    )
    headers = auth_header(user)
    response = auth_client.post(
        "/api/v1/admin/knowledge/documents",
        headers=headers,
        files={"file": ("guide.pdf", b"%PDF-test", "application/pdf")},
        data={"display_name": "Goa Guide", "destination": "Goa", "category": "travel_guide", "document_type": "destination_guide"},
    )
    assert response.status_code == 201
    source_id = response.json()["id"]
    assert auth_client.get("/api/v1/admin/knowledge/documents", headers=headers).status_code == 200
    assert auth_client.get(f"/api/v1/admin/knowledge/documents/{source_id}", headers=headers).status_code == 200

    removed = auth_client.delete(f"/api/v1/admin/knowledge/documents/{source_id}", headers=headers)
    assert removed.status_code == 200
    assert deleted == [{"where": {"document_id": "document-1"}}]