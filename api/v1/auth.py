from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from models.api_schemas import AuthResponse, LoginRequest, RegisterRequest
from services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _auth_service() -> AuthService:
    return AuthService()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    try:
        return service.register(db, payload.name, payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    try:
        return service.login(db, payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh")
def refresh():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Token refresh is not available yet.")


@router.post("/logout")
def logout():
    return {"message": "Logged out successfully."}