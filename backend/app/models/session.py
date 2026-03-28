from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PronunciationSession(Base):
    __tablename__ = "pronunciation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    language: Mapped[str] = mapped_column(String(16), nullable=False)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    phonemes_expected: Mapped[str] = mapped_column(Text, nullable=False)
    phonemes_actual: Mapped[str] = mapped_column(Text, nullable=False)

    score_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    score_fluency: Mapped[float] = mapped_column(Float, nullable=False)
    score_phoneme: Mapped[float] = mapped_column(Float, nullable=False)
    score_total: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    mouth_metrics: Mapped[dict | None] = mapped_column(SQLiteJSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="sessions")

