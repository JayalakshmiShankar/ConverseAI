from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.session import PronunciationSession
from app.models.user import User
from app.schemas.sessions import DashboardResponse, SessionCreateResponse, SessionListItem, SessionListResponse
from app.services.feedback import build_feedback
from app.services.languages import assert_supported_language
from app.services.phonemes import pseudo_phonemes
from app.services.scoring import score_pronunciation
from app.services.stt import SttNotConfiguredError, transcribe_with_whisper


router = APIRouter()


@router.post("", response_model=SessionCreateResponse)
async def create_session(
    language: str = Form(...),
    reference_text: str | None = Form(None),
    mouth_metrics: str | None = Form(None),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionCreateResponse:
    try:
        lang = assert_supported_language(language)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language") from e

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file")

    try:
        transcript = transcribe_with_whisper(audio_bytes, audio.filename or "audio.webm", lang)
    except SttNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="STT failed") from e

    expected_text = (reference_text or transcript).strip()
    expected_ph = pseudo_phonemes(expected_text, language)
    actual_ph = pseudo_phonemes(transcript, language)

    scores = score_pronunciation(expected_ph, actual_ph, transcript)
    feedback_text = build_feedback(language, expected_ph, actual_ph)

    parsed_mouth: dict | None = None
    if mouth_metrics:
        try:
            parsed_mouth = json.loads(mouth_metrics)
        except Exception:
            parsed_mouth = None

    session = PronunciationSession(
        user_id=current_user.id,
        language=language,
        reference_text=reference_text,
        transcript=transcript,
        phonemes_expected=" ".join(expected_ph),
        phonemes_actual=" ".join(actual_ph),
        score_accuracy=scores.accuracy,
        score_fluency=scores.fluency,
        score_phoneme=scores.phoneme,
        score_total=scores.total,
        confidence=scores.confidence,
        feedback_text=feedback_text,
        mouth_metrics=parsed_mouth,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionCreateResponse(
        session_id=session.id,
        transcript=session.transcript,
        phonemes_expected=session.phonemes_expected.split(" ") if session.phonemes_expected else [],
        phonemes_actual=session.phonemes_actual.split(" ") if session.phonemes_actual else [],
        score=session.score_total,
        confidence=session.confidence,
        feedback_text=session.feedback_text,
        created_at=session.created_at,
        mouth_metrics=session.mouth_metrics,
    )


@router.get("", response_model=SessionListResponse)
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionListResponse:
    rows = db.scalars(
        select(PronunciationSession)
        .where(PronunciationSession.user_id == current_user.id)
        .order_by(desc(PronunciationSession.created_at))
        .limit(20)
    ).all()

    items = [
        SessionListItem(
            session_id=s.id,
            language=s.language,
            score=s.score_total,
            confidence=s.confidence,
            transcript=s.transcript,
            created_at=s.created_at,
        )
        for s in rows
    ]
    return SessionListResponse(items=items)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    now = datetime.now(timezone.utc)
    last_7 = now - timedelta(days=7)

    avg_score = db.scalar(
        select(func.avg(PronunciationSession.score_total)).where(
            PronunciationSession.user_id == current_user.id,
            PronunciationSession.created_at >= last_7,
        )
    )

    recent_rows = db.scalars(
        select(PronunciationSession)
        .where(PronunciationSession.user_id == current_user.id)
        .order_by(desc(PronunciationSession.created_at))
        .limit(5)
    ).all()

    recent = [
        SessionListItem(
            session_id=s.id,
            language=s.language,
            score=s.score_total,
            confidence=s.confidence,
            transcript=s.transcript,
            created_at=s.created_at,
        )
        for s in recent_rows
    ]

    days = {
        s.created_at.date()
        for s in db.scalars(
            select(PronunciationSession.created_at).where(PronunciationSession.user_id == current_user.id)
        ).all()
    }
    streak = 0
    d = now.date()
    while d in days:
        streak += 1
        d = d - timedelta(days=1)

    return DashboardResponse(avg_score_last_7=round(float(avg_score or 0.0), 2), streak_days=streak, recent_sessions=recent)

