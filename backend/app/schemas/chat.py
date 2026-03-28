from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    language: str
    user_text: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    assistant_text: str

