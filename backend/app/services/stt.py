from __future__ import annotations

import io

from openai import OpenAI

from app.core.config import settings
from app.services.languages import LanguageSpec


class SttNotConfiguredError(RuntimeError):
    pass


def transcribe_with_whisper(audio_bytes: bytes, filename: str, language: LanguageSpec) -> str:
    if not settings.openai_api_key:
        raise SttNotConfiguredError("OPENAI_API_KEY not configured")

    client = OpenAI(api_key=settings.openai_api_key)
    f = io.BytesIO(audio_bytes)
    f.name = filename
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        language=language.stt_code,
        response_format="text",
    )
    if isinstance(result, str):
        return result.strip()
    return str(result).strip()

