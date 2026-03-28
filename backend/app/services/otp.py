from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.otp import OtpChallenge


def generate_otp(length: int = 6) -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def create_login_otp(db: Session, user_id: str) -> tuple[OtpChallenge, str]:
    otp = generate_otp()
    now = datetime.now(timezone.utc)
    challenge = OtpChallenge(
        user_id=user_id,
        purpose="login",
        otp_hash=hash_password(otp),
        expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge, otp


def verify_login_otp(db: Session, challenge_id: str, otp: str) -> str | None:
    challenge = db.get(OtpChallenge, challenge_id)
    if challenge is None:
        return None

    now = datetime.now(timezone.utc)
    if challenge.purpose != "login":
        return None
    if challenge.consumed_at is not None:
        return None
    if challenge.expires_at < now:
        return None
    if not verify_password(otp, challenge.otp_hash):
        return None

    challenge.consumed_at = now
    db.add(challenge)
    db.commit()
    return challenge.user_id

