from __future__ import annotations

from pydantic import BaseModel


class LanguageOut(BaseModel):
    id: str
    label: str


class LanguagesResponse(BaseModel):
    items: list[LanguageOut]

