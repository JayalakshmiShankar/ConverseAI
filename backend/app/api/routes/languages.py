from __future__ import annotations

from fastapi import APIRouter

from app.schemas.languages import LanguagesResponse, LanguageOut
from app.services.languages import SUPPORTED_LANGUAGES


router = APIRouter()


@router.get("", response_model=LanguagesResponse)
def list_languages() -> LanguagesResponse:
    items = [LanguageOut(id=spec.id, label=spec.label) for spec in SUPPORTED_LANGUAGES.values()]
    items.sort(key=lambda x: x.label)
    return LanguagesResponse(items=items)

