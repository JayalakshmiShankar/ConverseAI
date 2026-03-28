from __future__ import annotations

from collections import Counter


EN_TIPS = {
    "th": "Your 'th' sound needs work. Place your tongue lightly between your teeth and push air out.",
    "r": "For English 'r', keep your tongue bunched and do not tap the roof of your mouth.",
    "l": "For 'l', touch the tip of your tongue to the ridge just behind your upper teeth.",
    "v": "For 'v', gently bite your lower lip and vibrate your voice.",
    "w": "For 'w', round your lips as if blowing and start the sound smoothly.",
}

DE_TIPS = {
    "ch": "For German 'ch', keep your tongue high and let air flow without voicing (like a soft hiss).",
    "r": "German 'r' often comes from the throat; avoid a strong English 'r' curl.",
    "sch": "German 'sch' is like English 'sh' but slightly more rounded lips.",
}

ES_TIPS = {
    "rr": "Spanish rolled 'rr' needs a tongue trill. Try quick repeated 't' sounds to build the trill.",
    "ll": "Spanish 'll' varies by region; start with a 'y' sound (as in 'yes') if unsure.",
}


def build_feedback(language_id: str, expected: list[str], actual: list[str]) -> str:
    if not expected or not actual:
        return "Record a short phrase clearly and try again."

    exp_counts = Counter(expected)
    act_counts = Counter(actual)

    missing = [p for p, c in exp_counts.items() if c > act_counts.get(p, 0)]
    extra = [p for p, c in act_counts.items() if c > exp_counts.get(p, 0)]

    tips: list[str] = []
    if language_id in {"en-US", "en-GB"}:
        for p in missing[:4]:
            if p in EN_TIPS:
                tips.append(EN_TIPS[p])
    elif language_id == "de-DE":
        for p in missing[:4]:
            if p in DE_TIPS:
                tips.append(DE_TIPS[p])
    elif language_id == "es-ES":
        for p in missing[:4]:
            if p in ES_TIPS:
                tips.append(ES_TIPS[p])

    summary_parts: list[str] = []
    if missing:
        summary_parts.append(f"Likely missed sounds: {', '.join(missing[:8])}.")
    if extra:
        summary_parts.append(f"Extra/inserted sounds: {', '.join(extra[:8])}.")

    if not summary_parts and not tips:
        return "Good clarity overall. Focus on consistent stress and smoother transitions between sounds."

    return " ".join(summary_parts + tips)

