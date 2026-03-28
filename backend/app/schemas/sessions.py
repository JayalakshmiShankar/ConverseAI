from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str
    transcript: str
    phonemes_expected: list[str]
    phonemes_actual: list[str]
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    feedback_text: str
    created_at: datetime
    mouth_metrics: dict | None = None


class SessionListItem(BaseModel):
    session_id: str
    language: str
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    transcript: str
    created_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionListItem]


class DashboardResponse(BaseModel):
    avg_score_last_7: float = Field(ge=0, le=100)
    streak_days: int = Field(ge=0)
    recent_sessions: list[SessionListItem]

