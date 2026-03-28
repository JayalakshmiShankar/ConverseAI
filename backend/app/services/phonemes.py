from __future__ import annotations

import re


def _tokenize(text: str) -> list[str]:
    text = text.lower().strip()
    text = re.sub(r"[^a-zA-Z0-9\s'’-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split(" ") if text else []


EN_DIGRAPHS = [
    "tch",
    "ch",
    "sh",
    "th",
    "ph",
    "ng",
    "qu",
    "ck",
    "wh",
]

DE_DIGRAPHS = ["sch", "ch", "ei", "ie", "eu", "äu", "sp", "st"]
ES_DIGRAPHS = ["ll", "rr", "ch", "qu", "gu"]


def _digraph_phonemes(word: str, digraphs: list[str]) -> list[str]:
    i = 0
    out: list[str] = []
    while i < len(word):
        matched = None
        for d in digraphs:
            if word.startswith(d, i):
                matched = d
                break
        if matched:
            out.append(matched)
            i += len(matched)
        else:
            out.append(word[i])
            i += 1
    return [p for p in out if p.strip()]


def pseudo_phonemes(text: str, language_id: str) -> list[str]:
    words = _tokenize(text)
    if not words:
        return []

    phonemes: list[str] = []

    if language_id in {"en-US", "en-GB"}:
        for w in words:
            phonemes.extend(_digraph_phonemes(w, EN_DIGRAPHS))
    elif language_id == "de-DE":
        for w in words:
            phonemes.extend(_digraph_phonemes(w, DE_DIGRAPHS))
    elif language_id == "es-ES":
        for w in words:
            phonemes.extend(_digraph_phonemes(w, ES_DIGRAPHS))
    elif language_id == "ja-JP":
        joined = "".join(words)
        joined = re.sub(r"[^a-z0-9]+", "", joined)
        phonemes.extend(list(joined))
    else:
        for w in words:
            phonemes.extend(list(w))

    return [p for p in phonemes if p and p != " "]

