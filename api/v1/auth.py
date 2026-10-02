import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from models.api_schemas import AuthResponse, ForgotPasswordRequest, LoginRequest, RefreshRequest, RegisterRequest, ResetPasswordRequest, UserResponse, VerifyEmailRequest
from services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _auth_service() -> AuthService:
    return AuthService()


def _invalid(detail: str = "Authentication request could not be completed.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


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
        raise _invalid("The email or password is incorrect.") from exc


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    try:
        return service.refresh(db, payload.refresh_token)
    except AuthError as exc:
        raise _invalid("Invalid refresh token.") from exc


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    service.logout(db, payload.refresh_token)
    return {"message": "Logged out successfully."}


@router.post("/verify-email", response_model=UserResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    try:
        return service.verify_email(db, payload.token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.") from exc


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    token = service.forgot_password(db, payload.email)
    response = {"message": "If the account exists, password reset instructions have been generated."}
    if token and os.getenv("PACK_GO_ENV", "development").lower() != "production":
        response["development_token"] = token
    return response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db), service: AuthService = Depends(_auth_service)):
    try:
        service.reset_password(db, payload.token, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"message": "Password reset successfully."}
