from __future__ import annotations

from openai import OpenAI

from app.core.config import settings
from app.services.languages import LanguageSpec


class ChatNotConfiguredError(RuntimeError):
    pass


def chat_reply(language: LanguageSpec, user_text: str) -> str:
    if not settings.openai_api_key:
        raise ChatNotConfiguredError("OPENAI_API_KEY not configured")

    client = OpenAI(api_key=settings.openai_api_key)

    system = (
        "You are a pronunciation practice partner for business professionals. "
        "Keep replies short (1-3 sentences). "
        "Ask the user to repeat a specific short phrase and vary it slightly each turn. "
        "If the language is English, keep vocabulary professional."
    )

    result = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Language: {language.label}\nUser: {user_text}"},
        ],
        temperature=0.7,
    )

    return (result.choices[0].message.content or "").strip() or "Please repeat: 'Thank you for your time.'"

