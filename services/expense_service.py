from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from database.models import Expense, ExpenseShare, Trip, TripMember, User
from models.api_schemas import ExpenseCreateRequest, ExpenseResponse, ExpenseSummaryResponse, ExpenseUpdateRequest
from services.collaboration_service import AccessDenied, TripAccessService

CENT = Decimal("0.01")


class ExpenseService:
    def __init__(self, db: Session):
        self.db = db
        self.access = TripAccessService(db)

    def _trip_and_actor(self, trip_id: str, actor_id: str) -> Trip:
        trip = self.access.get_trip_for_member(trip_id, actor_id)
        if not trip.is_group and trip.user_id != actor_id:
            raise AccessDenied("Trip not found.")
        return trip

    def _eligible_user_ids(self, trip: Trip) -> set[str]:
        if trip.is_group:
            rows = self.db.scalars(
                select(TripMember.user_id)
                .join(User, User.id == TripMember.user_id)
                .where(TripMember.trip_id == trip.id, TripMember.status == "active", User.is_active.is_(True))
            ).all()
            return set(rows)
        return {trip.user_id} if trip.user_id else set()

    def _validate_users(self, trip: Trip, user_ids: set[str]) -> None:
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
    def _replace_shares(expense: Expense, shares: list[tuple[str, Decimal]]) -> None:
        existing = {item.user_id: item for item in expense.participants}
        requested_ids = {user_id for user_id, _ in shares}
        for user_id in set(existing) - requested_ids:
            expense.participants.remove(existing[user_id])
        for user_id, amount in shares:
            if user_id in existing:
                existing[user_id].amount = amount
            else:
                expense.participants.append(ExpenseShare(id=str(uuid4()), user_id=user_id, amount=amount))

    def _commit(self) -> None:
        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise RuntimeError("Unable to save expense.") from exc

    def _expense(self, expense_id: str, actor_id: str) -> Expense:
        expense = self.db.scalar(
            select(Expense)
            .options(selectinload(Expense.participants).selectinload(ExpenseShare.user), selectinload(Expense.payer))
            .where(Expense.id == expense_id)
        )
        if expense is None:
            raise AccessDenied("Expense not found.")
        self._trip_and_actor(expense.trip_id, actor_id)
        return expense

    @staticmethod
    def _response(expense: Expense) -> ExpenseResponse:
        return ExpenseResponse(
            id=expense.id,
            trip_id=expense.trip_id,
            created_by_user_id=expense.created_by_user_id,
            payer_user_id=expense.payer_user_id,
            payer_name=expense.payer.name,
            amount=expense.amount,
            category=expense.category,
            expense_date=expense.expense_date,
            description=expense.description,
            split_type=expense.split_type,
            participants=[
                {"user_id": share.user_id, "name": share.user.name, "amount": share.amount}
                for share in sorted(expense.participants, key=lambda item: item.user_id)
            ],
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )

    def list_expenses(self, trip_id: str, actor_id: str) -> list[ExpenseResponse]:
        self._trip_and_actor(trip_id, actor_id)
        rows = self.db.scalars(
            select(Expense)
            .options(selectinload(Expense.participants).selectinload(ExpenseShare.user), selectinload(Expense.payer))
            .where(Expense.trip_id == trip_id)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc(), Expense.id)
        ).all()
        return [self._response(row) for row in rows]

    def create(self, trip_id: str, actor_id: str, payload: ExpenseCreateRequest) -> ExpenseResponse:
        trip = self._trip_and_actor(trip_id, actor_id)
        payer_id = payload.payer_user_id or actor_id
        participant_ids = [item.user_id for item in payload.participants]
        self._validate_users(trip, set(participant_ids) | {payer_id})
        amount = payload.amount.quantize(CENT)
        shares = self._equal_shares(amount, participant_ids) if payload.split_type == "equal" else self._custom_shares(payload.participants)
        if sum((share for _, share in shares), Decimal("0")) != amount:
            raise ValueError("Participant shares must equal the expense amount.")

        expense = Expense(
            id=str(uuid4()), trip_id=trip_id, created_by_user_id=actor_id,
            payer_user_id=payer_id, amount=amount, category=payload.category,
            expense_date=payload.expense_date,
            description=payload.description.strip() if payload.description else None,
            split_type=payload.split_type,
        )
        self._replace_shares(expense, shares)
        self.db.add(expense)
        self._commit()
        return self._response(expense)

    def update(self, expense_id: str, actor_id: str, payload: ExpenseUpdateRequest) -> ExpenseResponse:
        expense = self._expense(expense_id, actor_id)
        trip = self._trip_and_actor(expense.trip_id, actor_id)
        if trip.is_group:
            member = self.access.member(trip.id, actor_id)
            if expense.created_by_user_id != actor_id and member.role not in {"owner", "admin"}:
                raise AccessDenied("Expense cannot be edited.")

        updates = payload.model_dump(exclude_unset=True)
        if "payer_user_id" in updates and updates["payer_user_id"] is None:
            raise ValueError("A payer is required.")
        for field in ("category", "expense_date", "description", "split_type"):
            if field in updates:
                value = updates[field]
                setattr(expense, field, value.strip() if field == "description" and value else value)
        if "amount" in updates:
            expense.amount = updates["amount"].quantize(CENT)

        participant_input = updates.get("participants")
        participant_ids = [item["user_id"] for item in participant_input] if participant_input is not None else [share.user_id for share in expense.participants]
        payer_id = updates.get("payer_user_id", expense.payer_user_id)
        self._validate_users(trip, set(participant_ids) | {payer_id})

        if participant_input is not None or "amount" in updates or "split_type" in updates:
            if expense.split_type == "equal":
                if participant_input is not None and any(item.get("amount") is not None for item in participant_input):
                    raise ValueError("Equal split participants must not include amounts.")
                shares = self._equal_shares(expense.amount, participant_ids)
            elif participant_input is not None:
                shares = self._custom_shares(participant_input)
            else:
                shares = [(share.user_id, share.amount) for share in expense.participants]
            if sum((share for _, share in shares), Decimal("0")) != expense.amount:
                raise ValueError("Participant shares must equal the expense amount.")
            self._replace_shares(expense, shares)
        if "payer_user_id" in updates:
            expense.payer_user_id = payer_id
        self._commit()
        return self._response(expense)

    def delete(self, expense_id: str, actor_id: str) -> None:
        expense = self._expense(expense_id, actor_id)
        trip = self._trip_and_actor(expense.trip_id, actor_id)
        if trip.is_group:
            member = self.access.member(trip.id, actor_id)
            if expense.created_by_user_id != actor_id and member.role not in {"owner", "admin"}:
                raise AccessDenied("Expense cannot be deleted.")
        self.db.delete(expense)
        self._commit()

    def summary(self, trip_id: str, actor_id: str) -> ExpenseSummaryResponse:
        self._trip_and_actor(trip_id, actor_id)
        expenses = self.db.scalars(
            select(Expense)
            .options(selectinload(Expense.participants).selectinload(ExpenseShare.user), selectinload(Expense.payer))
            .where(Expense.trip_id == trip_id)
        ).all()
        paid: dict[str, Decimal] = {}
        owed: dict[str, Decimal] = {}
        names: dict[str, str] = {}
        category_totals: dict[str, Decimal] = {}
        date_totals: dict[str, Decimal] = {}
        total = Decimal("0.00")
        for expense in expenses:
            total += expense.amount
            paid[expense.payer_user_id] = paid.get(expense.payer_user_id, Decimal("0.00")) + expense.amount
            names[expense.payer_user_id] = expense.payer.name
            category_totals[expense.category] = category_totals.get(expense.category, Decimal("0.00")) + expense.amount
            date_key = expense.expense_date.isoformat()
            date_totals[date_key] = date_totals.get(date_key, Decimal("0.00")) + expense.amount
            for share in expense.participants:
                owed[share.user_id] = owed.get(share.user_id, Decimal("0.00")) + share.amount
                names[share.user_id] = share.user.name

        participant_ids = sorted(set(paid) | set(owed))
        balances = {user_id: paid.get(user_id, Decimal("0.00")) - owed.get(user_id, Decimal("0.00")) for user_id in participant_ids}
        participants = [
            {"user_id": user_id, "name": names[user_id], "total_paid": paid.get(user_id, Decimal("0.00")), "total_owed": owed.get(user_id, Decimal("0.00")), "balance": balances[user_id]}
            for user_id in participant_ids
        ]
        debtors = [[user_id, -balance] for user_id, balance in sorted(balances.items()) if balance < 0]
        creditors = [[user_id, balance] for user_id, balance in sorted(balances.items()) if balance > 0]
        settlements = []
        debtor_index = creditor_index = 0
        while debtor_index < len(debtors) and creditor_index < len(creditors):
            debtor_id, debt = debtors[debtor_index]
            creditor_id, credit = creditors[creditor_index]
            transfer = min(debt, credit).quantize(CENT)
            settlements.append({"from_user_id": debtor_id, "from_name": names[debtor_id], "to_user_id": creditor_id, "to_name": names[creditor_id], "amount": transfer})
            debtors[debtor_index][1] -= transfer
            creditors[creditor_index][1] -= transfer
            if debtors[debtor_index][1] == 0:
                debtor_index += 1
            if creditors[creditor_index][1] == 0:
                creditor_index += 1

        return ExpenseSummaryResponse(
            trip_id=trip_id, expense_count=len(expenses), total_expenses=total,
            category_totals=category_totals, date_totals=date_totals,
            participants=participants, settlements=settlements,
        )
