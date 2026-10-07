from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from bson.decimal128 import Decimal128
from pymongo.database import Database

from models.api_schemas import ExpenseCreateRequest, ExpenseResponse, ExpenseSummaryResponse, ExpenseUpdateRequest
from services.collaboration_service import AccessDenied, TripAccessService

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class ExpenseService:
    def __init__(self, database: Database):
        self.database = database
        self.access = TripAccessService(database)

    def _trip_and_actor(self, trip_id: str, actor_id: str) -> dict:
        trip = self.access.get_trip_for_member(trip_id, actor_id)
        if not trip.get("is_group") and trip.get("user_id") != actor_id:
            raise AccessDenied("Trip not found.")
        return trip

    def _eligible_user_ids(self, trip: dict) -> set[str]:
        if trip.get("is_group"):
            return {
                member["user_id"] for member in trip.get("members", [])
                if member.get("status") == "active"
                and self.database.users.find_one(
                    {"_id": member["user_id"], "is_active": True}, {"_id": 1}
                )
            }
        return {trip["user_id"]} if trip.get("user_id") else set()

    def _validate_users(self, trip: dict, user_ids: set[str]) -> None:
        if user_ids - self._eligible_user_ids(trip):
            raise ValueError("Payer and participants must be active members of this trip.")

    @staticmethod
    def _equal_shares(amount: Decimal, user_ids: list[str]) -> list[tuple[str, Decimal]]:
        ordered_ids = sorted(user_ids)
        if not ordered_ids:
            raise ValueError("At least one expense participant is required.")
        cents = int(amount * 100)
        base, remainder = divmod(cents, len(ordered_ids))
        return [
            (user_id, Decimal(base + (1 if index < remainder else 0)) / 100)
            for index, user_id in enumerate(ordered_ids)
        ]

    @staticmethod
    def _custom_shares(participants) -> list[tuple[str, Decimal]]:
        if any((item.get("amount") if isinstance(item, dict) else item.amount) is None for item in participants):
            raise ValueError("Custom split participants must include an amount.")
        return [
            (item["user_id"], item["amount"]) if isinstance(item, dict) else (item.user_id, item.amount)
            for item in participants
        ]

    @staticmethod
    def _stored_amount(amount: Decimal) -> Decimal128:
        return Decimal128(amount.quantize(CENT))

    @staticmethod
    def _amount(value) -> Decimal:
        return value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value))

    def _expense(self, expense_id: str, actor_id: str) -> dict:
        expense = self.database.expenses.find_one({"_id": expense_id})
        if expense is None:
            raise AccessDenied("Expense not found.")
        self._trip_and_actor(expense["trip_id"], actor_id)
        return expense

    def _response(self, expense: dict) -> ExpenseResponse:
        payer = self.database.users.find_one({"_id": expense["payer_user_id"]}, {"name": 1})
        participants = []
        for share in sorted(expense.get("participants", []), key=lambda item: item["user_id"]):
            user = self.database.users.find_one({"_id": share["user_id"]}, {"name": 1})
            participants.append({
                "user_id": share["user_id"],
                "name": user["name"] if user else share["user_id"],
                "amount": self._amount(share["amount"]),
            })
        return ExpenseResponse(
            id=expense["id"],
            trip_id=expense["trip_id"],
            created_by_user_id=expense["created_by_user_id"],
            payer_user_id=expense["payer_user_id"],
            payer_name=payer["name"] if payer else expense["payer_user_id"],
            amount=self._amount(expense["amount"]),
            category=expense["category"],
            expense_date=date.fromisoformat(expense["expense_date"]),
            description=expense.get("description"),
            split_type=expense["split_type"],
            participants=participants,
            created_at=expense["created_at"],
            updated_at=expense["updated_at"],
        )

    def list_expenses(self, trip_id: str, actor_id: str) -> list[ExpenseResponse]:
        self._trip_and_actor(trip_id, actor_id)
        rows = self.database.expenses.find({"trip_id": trip_id}).sort(
            [("expense_date", -1), ("created_at", -1), ("_id", 1)]
        )
        return [self._response(row) for row in rows]

    def create(self, trip_id: str, actor_id: str, payload: ExpenseCreateRequest) -> ExpenseResponse:
        trip = self._trip_and_actor(trip_id, actor_id)
        payer_id = payload.payer_user_id or actor_id
        participant_ids = [item.user_id for item in payload.participants]
        self._validate_users(trip, set(participant_ids) | {payer_id})
        amount = payload.amount.quantize(CENT)
        shares = self._equal_shares(amount, participant_ids) if payload.split_type == "equal" else self._custom_shares(payload.participants)
        if sum((share for _, share in shares), ZERO) != amount:
            raise ValueError("Participant shares must equal the expense amount.")

        now = datetime.now(UTC)
        expense_id = str(uuid4())
        expense = {
            "_id": expense_id,
            "id": expense_id,
            "trip_id": trip_id,
            "created_by_user_id": actor_id,
            "payer_user_id": payer_id,
            "amount": self._stored_amount(amount),
            "category": payload.category,
            "expense_date": payload.expense_date.isoformat(),
            "description": payload.description.strip() if payload.description else None,
            "split_type": payload.split_type,
            "participants": [
                {"id": str(uuid4()), "user_id": user_id, "amount": self._stored_amount(share)}
                for user_id, share in shares
            ],
            "created_at": now,
            "updated_at": now,
        }
        self.database.expenses.insert_one(expense)
        return self._response(expense)

    def update(self, expense_id: str, actor_id: str, payload: ExpenseUpdateRequest) -> ExpenseResponse:
        expense = self._expense(expense_id, actor_id)
        trip = self._trip_and_actor(expense["trip_id"], actor_id)
        if trip.get("is_group"):
            member = self.access.member(trip["_id"], actor_id)
            if expense["created_by_user_id"] != actor_id and member["role"] not in {"owner", "admin"}:
                raise AccessDenied("Expense cannot be edited.")

        updates = payload.model_dump(exclude_unset=True)
        if "payer_user_id" in updates and updates["payer_user_id"] is None:
            raise ValueError("A payer is required.")
        for field in ("category", "expense_date", "description", "split_type"):
            if field in updates:
                value = updates[field]
                if field == "expense_date":
                    value = value.isoformat()
                elif field == "description" and value:
                    value = value.strip()
                expense[field] = value
        if "amount" in updates:
            expense["amount"] = self._stored_amount(updates["amount"])

        participant_input = updates.get("participants")
        participant_ids = [item["user_id"] for item in participant_input] if participant_input is not None else [share["user_id"] for share in expense["participants"]]
        payer_id = updates.get("payer_user_id", expense["payer_user_id"])
        self._validate_users(trip, set(participant_ids) | {payer_id})

        if participant_input is not None or "amount" in updates or "split_type" in updates:
            if expense["split_type"] == "equal":
                if participant_input is not None and any(item.get("amount") is not None for item in participant_input):
                    raise ValueError("Equal split participants must not include amounts.")
                shares = self._equal_shares(self._amount(expense["amount"]), participant_ids)
            elif participant_input is not None:
                shares = self._custom_shares(participant_input)
            else:
                shares = [(share["user_id"], self._amount(share["amount"])) for share in expense["participants"]]
            if sum((share for _, share in shares), ZERO) != self._amount(expense["amount"]):
                raise ValueError("Participant shares must equal the expense amount.")
            expense["participants"] = [
                {"id": str(uuid4()), "user_id": user_id, "amount": self._stored_amount(share)}
                for user_id, share in shares
            ]
        if "payer_user_id" in updates:
            expense["payer_user_id"] = payer_id

        expense["updated_at"] = datetime.now(UTC)
        self.database.expenses.replace_one({"_id": expense_id}, expense)
        return self._response(expense)

    def delete(self, expense_id: str, actor_id: str) -> None:
        expense = self._expense(expense_id, actor_id)
        trip = self._trip_and_actor(expense["trip_id"], actor_id)
        if trip.get("is_group"):
            member = self.access.member(trip["_id"], actor_id)
            if expense["created_by_user_id"] != actor_id and member["role"] not in {"owner", "admin"}:
                raise AccessDenied("Expense cannot be deleted.")
        self.database.expenses.delete_one({"_id": expense_id})

    def summary(self, trip_id: str, actor_id: str) -> ExpenseSummaryResponse:
        self._trip_and_actor(trip_id, actor_id)
        expenses = list(self.database.expenses.find({"trip_id": trip_id}))
        paid: dict[str, Decimal] = {}
        owed: dict[str, Decimal] = {}
        names: dict[str, str] = {}
        category_totals: dict[str, Decimal] = {}
        date_totals: dict[str, Decimal] = {}
        total = ZERO
        for expense in expenses:
            amount = self._amount(expense["amount"])
            payer_id = expense["payer_user_id"]
            payer = self.database.users.find_one({"_id": payer_id}, {"name": 1})
            names[payer_id] = payer["name"] if payer else payer_id
            paid[payer_id] = paid.get(payer_id, ZERO) + amount
            total += amount
            category = expense["category"]
            category_totals[category] = category_totals.get(category, ZERO) + amount
            day = expense["expense_date"]
            date_totals[day] = date_totals.get(day, ZERO) + amount
            for share in expense.get("participants", []):
                user_id = share["user_id"]
                user = self.database.users.find_one({"_id": user_id}, {"name": 1})
                names[user_id] = user["name"] if user else user_id
                owed[user_id] = owed.get(user_id, ZERO) + self._amount(share["amount"])

        participant_ids = sorted(set(paid) | set(owed))
        balances = {uid: paid.get(uid, ZERO) - owed.get(uid, ZERO) for uid in participant_ids}
        participants = [
            {
                "user_id": uid, "name": names[uid],
                "total_paid": paid.get(uid, ZERO), "total_owed": owed.get(uid, ZERO),
                "balance": balances[uid],
            }
            for uid in participant_ids
        ]
        debtors = [[uid, -balance] for uid, balance in sorted(balances.items()) if balance < 0]
        creditors = [[uid, balance] for uid, balance in sorted(balances.items()) if balance > 0]
        settlements = []
        debtor_index = creditor_index = 0
        while debtor_index < len(debtors) and creditor_index < len(creditors):
            debtor_id, debt = debtors[debtor_index]
            creditor_id, credit = creditors[creditor_index]
            transfer = min(debt, credit).quantize(CENT)
            settlements.append({
                "from_user_id": debtor_id, "from_name": names[debtor_id],
                "to_user_id": creditor_id, "to_name": names[creditor_id],
                "amount": transfer,
            })
            debtors[debtor_index][1] -= transfer
            creditors[creditor_index][1] -= transfer
            if debtors[debtor_index][1] == 0:
                debtor_index += 1
            if creditors[creditor_index][1] == 0:
                creditor_index += 1
        return ExpenseSummaryResponse(
            trip_id=trip_id,
            expense_count=len(expenses),
            total_expenses=total,
            category_totals=category_totals,
            date_totals=date_totals,
            participants=participants,
            settlements=settlements,
        )
