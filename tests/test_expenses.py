import importlib
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def expense_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'expenses.db').as_posix()}")
    monkeypatch.setenv("PACK_GO_JWT_SECRET", "local-development-secret-1234567890")
    import database.connection as connection
    import database as database_module
    importlib.reload(connection)
    importlib.reload(database_module)
    from database.base import Base
    Base.metadata.create_all(bind=connection.engine)
    import main
    main = importlib.reload(main)

    def register(name, email):
        client = TestClient(main.app)
        auth = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "password123"}).json()
        client.headers.update({"Authorization": f"Bearer {auth['access_token']}"})
        return client, auth["user"]

    return register("Owner", "owner@example.com"), register("Member", "member@example.com"), register("Outsider", "outsider@example.com")


def _group_trip(owner_client, member_user):
    trip = owner_client.post("/api/v1/trips", json={"title": "Shared", "destination": "Goa", "duration": 3, "total_budget": 1000, "itinerary": []}).json()
    trip_id = trip["id"]
    assert owner_client.post(f"/api/v1/trips/{trip_id}/group").status_code == 200
    invite = owner_client.post(f"/api/v1/trips/{trip_id}/invitations", json={"invitee_user_id": member_user["id"]}).json()
    return trip_id, invite["token"]


def test_expense_crud_equal_custom_splits_and_settlement(expense_clients):
    (owner, owner_user), (member, member_user), _ = expense_clients
    trip_id, token = _group_trip(owner, member_user)
    assert member.post(f"/api/v1/invitations/{token}/accept").status_code == 200

    endpoint = f"/api/v1/trips/{trip_id}/expenses"
    forbidden_actor = owner.post(endpoint, json={
        "amount": "10.00", "category": "food", "participants": [{"user_id": owner_user["id"]}],
        "created_by_user_id": member_user["id"],
    })
    assert forbidden_actor.status_code == 422
    created = owner.post(endpoint, json={
        "amount": "10.00", "payer_user_id": member_user["id"], "category": "food", "expense_date": "2026-09-01",
        "description": "Lunch", "split_type": "equal", "participants": [{"user_id": owner_user["id"]}, {"user_id": member_user["id"]}],
    })
    assert created.status_code == 201, created.text
    expense = created.json()
    assert expense["created_by_user_id"] == owner_user["id"]
    assert expense["payer_user_id"] == member_user["id"]
    assert sorted(Decimal(row["amount"]) for row in expense["participants"]) == [Decimal("5.00"), Decimal("5.00")]

    custom = member.post(endpoint, json={
        "amount": "12.00", "category": "transport", "expense_date": "2026-09-02", "split_type": "custom",
        "participants": [{"user_id": owner_user["id"], "amount": "7.00"}, {"user_id": member_user["id"], "amount": "5.00"}],
    })
    assert custom.status_code == 201, custom.text

    listed = member.get(endpoint)
    assert listed.status_code == 200 and len(listed.json()) == 2
    summary = owner.get(f"{endpoint}/summary").json()
    assert Decimal(summary["total_expenses"]) == Decimal("22.00")
    by_user = {row["user_id"]: row for row in summary["participants"]}
    assert Decimal(by_user[owner_user["id"]]["total_paid"]) == Decimal("0.00")
    assert Decimal(by_user[member_user["id"]]["total_paid"]) == Decimal("22.00")
    assert Decimal(by_user[owner_user["id"]]["total_owed"]) == Decimal("12.00")
    assert Decimal(by_user[member_user["id"]]["total_owed"]) == Decimal("10.00")
    assert Decimal(by_user[owner_user["id"]]["balance"]) == Decimal("-12.00")
    assert Decimal(by_user[member_user["id"]]["balance"]) == Decimal("12.00")
    assert sum((Decimal(item["amount"]) for item in summary["settlements"]), Decimal("0")) == Decimal("12.00")
    assert summary["category_totals"] == {"food": "10.00", "transport": "12.00"}
    assert summary["date_totals"] == {"2026-09-01": "10.00", "2026-09-02": "12.00"}
    incomplete_custom_edit = member.patch(f"/api/v1/expenses/{custom.json()['id']}", json={
        "participants": [{"user_id": owner_user["id"]}, {"user_id": member_user["id"]}],
    })
    assert incomplete_custom_edit.status_code == 422

    updated = owner.patch(f"/api/v1/expenses/{expense['id']}", json={"description": "Updated lunch", "amount": "11.00"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Updated lunch"
    assert sum(Decimal(row["amount"]) for row in updated.json()["participants"]) == Decimal("11.00")
    assert owner.delete(f"/api/v1/expenses/{expense['id']}").status_code == 204
    assert len(owner.get(endpoint).json()) == 1


def test_invalid_payer_participants_and_custom_totals_rejected(expense_clients):
    (owner, owner_user), (member, member_user), (_, outsider_user) = expense_clients
    trip_id, token = _group_trip(owner, member_user)
    assert member.post(f"/api/v1/invitations/{token}/accept").status_code == 200
    endpoint = f"/api/v1/trips/{trip_id}/expenses"
    payload = {"amount": "10.00", "category": "food", "participants": [{"user_id": owner_user["id"]}]}
    assert owner.post(endpoint, json={**payload, "payer_user_id": outsider_user["id"]}).status_code == 422
    assert owner.post(endpoint, json={**payload, "participants": [{"user_id": outsider_user["id"]}]}).status_code == 422
    assert owner.post(endpoint, json={**payload, "split_type": "custom", "participants": [{"user_id": owner_user["id"], "amount": "9.99"}]}).status_code == 422
    assert owner.post(endpoint, json={**payload, "amount": "0"}).status_code == 422


def test_unauthorized_cross_trip_and_inactive_member_access(expense_clients):
    (owner, owner_user), (member, member_user), (outsider, _) = expense_clients
    trip_id, token = _group_trip(owner, member_user)
    assert member.post(f"/api/v1/invitations/{token}/accept").status_code == 200
    created = member.post(f"/api/v1/trips/{trip_id}/expenses", json={
        "amount": "8.00", "category": "food", "participants": [{"user_id": owner_user["id"]}, {"user_id": member_user["id"]}],
    }).json()
    assert outsider.get(f"/api/v1/trips/{trip_id}/expenses").status_code == 404
    assert outsider.patch(f"/api/v1/expenses/{created['id']}", json={"description": "No"}).status_code == 404
    assert owner.delete(f"/api/v1/trips/{trip_id}/members/{member_user['id']}").status_code == 204
    assert member.get(f"/api/v1/trips/{trip_id}/expenses").status_code == 404
    assert member.get(f"/api/v1/trips/{trip_id}/expenses/summary").status_code == 404


def test_group_member_cannot_edit_or_delete_another_members_expense(expense_clients):
    (owner, owner_user), (member, member_user), _ = expense_clients
    trip_id, token = _group_trip(owner, member_user)
    assert member.post(f"/api/v1/invitations/{token}/accept").status_code == 200
    created = owner.post(f"/api/v1/trips/{trip_id}/expenses", json={
        "amount": "8.00", "category": "food", "participants": [{"user_id": owner_user["id"]}],
    }).json()
    assert member.patch(f"/api/v1/expenses/{created['id']}", json={"description": "No"}).status_code == 403
    assert member.delete(f"/api/v1/expenses/{created['id']}").status_code == 403


def test_personal_trip_only_owner_can_access_expenses(expense_clients):
    (owner, owner_user), (_, member_user), _ = expense_clients
    trip = owner.post("/api/v1/trips", json={"title": "Personal", "destination": "Kyoto", "duration": 2, "total_budget": 500, "itinerary": []}).json()
    endpoint = f"/api/v1/trips/{trip['id']}/expenses"
    payload = {"amount": "5.00", "category": "other", "participants": [{"user_id": owner_user["id"]}]}
    assert owner.post(endpoint, json=payload).status_code == 201
    assert owner.post(endpoint, json={**payload, "payer_user_id": member_user["id"]}).status_code == 422
