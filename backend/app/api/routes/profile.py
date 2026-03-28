from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileOut


router = APIRouter()


@router.get("", response_model=ProfileOut)
def get_profile(current_user: User = Depends(get_current_user)) -> ProfileOut:
    if current_user.profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    p = current_user.profile
    return ProfileOut(name=p.name, date_of_birth=p.date_of_birth, gender=p.gender, mobile_number=p.mobile_number)


@router.post("", response_model=ProfileOut)
def create_or_update_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileOut:
    profile = db.scalar(select(Profile).where(Profile.user_id == current_user.id))
    if profile is None:
        profile = Profile(user_id=current_user.id, **payload.model_dump())
        db.add(profile)
    else:
        for k, v in payload.model_dump().items():
            setattr(profile, k, v)
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return ProfileOut(
        name=profile.name,
        date_of_birth=profile.date_of_birth,
        gender=profile.gender,
        mobile_number=profile.mobile_number,
    )

