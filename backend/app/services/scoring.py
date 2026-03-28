from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBreakdown:
    accuracy: float
    fluency: float
    phoneme: float
    total: float
    confidence: float


def levenshtein_distance(a: list[str], b: list[str]) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def score_pronunciation(expected_phonemes: list[str], actual_phonemes: list[str], transcript: str) -> ScoreBreakdown:
    max_len = max(len(expected_phonemes), len(actual_phonemes), 1)
    dist = levenshtein_distance(expected_phonemes, actual_phonemes)
    phoneme_score = max(0.0, 1.0 - (dist / max_len)) * 100.0

    word_count = len([w for w in transcript.split(" ") if w.strip()])
    fluency = min(100.0, (word_count / max(1, len(transcript) / 6.0)) * 100.0)
    accuracy = min(100.0, max(0.0, phoneme_score * 0.8 + fluency * 0.2))

    total = 0.5 * accuracy + 0.3 * fluency + 0.2 * phoneme_score
    confidence = min(1.0, max(0.1, (total / 100.0) * 0.9 + 0.1))

    return ScoreBreakdown(
        accuracy=round(accuracy, 2),
        fluency=round(fluency, 2),
        phoneme=round(phoneme_score, 2),
        total=round(total, 2),
        confidence=round(confidence, 3),
    )

