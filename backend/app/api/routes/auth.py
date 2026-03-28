from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginChallengeResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    VerifyOtpRequest,
)
from app.services.otp import create_login_otp, verify_login_otp


router = APIRouter()


@router.post("/register", response_model=LoginChallengeResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> LoginChallengeResponse:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password), is_email_verified=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    challenge, otp = create_login_otp(db, user.id)
    otp_debug = otp if settings.otp_debug_return and settings.app_env != "production" else None
    return LoginChallengeResponse(
        challenge_id=challenge.id,
        expires_in_seconds=max(0, int((challenge.expires_at - datetime.now(timezone.utc)).total_seconds())),
        otp_debug=otp_debug,
    )


@router.post("/login", response_model=LoginChallengeResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginChallengeResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    challenge, otp = create_login_otp(db, user.id)
    otp_debug = otp if settings.otp_debug_return and settings.app_env != "production" else None
    return LoginChallengeResponse(
        challenge_id=challenge.id,
        expires_in_seconds=max(0, int((challenge.expires_at - datetime.now(timezone.utc)).total_seconds())),
        otp_debug=otp_debug,
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user_id = verify_login_otp(db, payload.challenge_id, payload.otp)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_email_verified:
        user.is_email_verified = True
        db.add(user)
        db.commit()

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"id": current_user.id, "email": current_user.email, "is_email_verified": current_user.is_email_verified}

