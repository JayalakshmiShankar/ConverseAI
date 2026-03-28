from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSpec:
    id: str
    label: str
    stt_code: str


SUPPORTED_LANGUAGES: dict[str, LanguageSpec] = {
    "en-US": LanguageSpec(id="en-US", label="English (US accent)", stt_code="en"),
    "en-GB": LanguageSpec(id="en-GB", label="English (UK accent)", stt_code="en"),
    "ja-JP": LanguageSpec(id="ja-JP", label="Japanese", stt_code="ja"),
    "de-DE": LanguageSpec(id="de-DE", label="German", stt_code="de"),
    "es-ES": LanguageSpec(id="es-ES", label="Spanish", stt_code="es"),
}


def assert_supported_language(language_id: str) -> LanguageSpec:
    spec = SUPPORTED_LANGUAGES.get(language_id)
    if spec is None:
        raise ValueError("Unsupported language")
    return spec

