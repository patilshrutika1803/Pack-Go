from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.v1.dependencies import get_current_user
from database import User
from database.connection import get_db
from models.api_schemas import ExpenseCreateRequest, ExpenseResponse, ExpenseSummaryResponse, ExpenseUpdateRequest
from services.collaboration_service import AccessDenied
from services.expense_service import ExpenseService

router = APIRouter(prefix="/api/v1", tags=["Expenses"])


def _raise_expense_error(exc: Exception) -> None:
    if isinstance(exc, AccessDenied):
        code = status.HTTP_404_NOT_FOUND if str(exc) in {"Trip not found.", "Expense not found."} else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    raise exc


@router.post("/trips/{trip_id}/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(trip_id: str, payload: ExpenseCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return ExpenseService(db).create(trip_id, user.id, payload)
    except (AccessDenied, ValueError) as exc:
        _raise_expense_error(exc)


@router.get("/trips/{trip_id}/expenses", response_model=list[ExpenseResponse])
def list_expenses(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return ExpenseService(db).list_expenses(trip_id, user.id)
    except AccessDenied as exc:
        _raise_expense_error(exc)


@router.get("/trips/{trip_id}/expenses/summary", response_model=ExpenseSummaryResponse)
def expense_summary(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return ExpenseService(db).summary(trip_id, user.id)
    except AccessDenied as exc:
        _raise_expense_error(exc)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: str, payload: ExpenseUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return ExpenseService(db).update(expense_id, user.id, payload)
    except (AccessDenied, ValueError) as exc:
        _raise_expense_error(exc)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ExpenseService(db).delete(expense_id, user.id)
    except AccessDenied as exc:
        _raise_expense_error(exc)
