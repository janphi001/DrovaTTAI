from __future__ import annotations

import re

from drova_voice.emotions import EmotionTag

KITTEN_MIN_INTENSITY = 0.3
_HIGH_AROUSAL = {"angry", "excited", "surprised", "joyful", "stern"}
_LOW_AROUSAL = {"sad", "tender", "contemplative", "mundane"}


def render_kitten(text: str, tag: EmotionTag) -> str:
    s = text
    n = len(text)
    placed = sorted(((max(0, min(ev.pos, n)), i, ev) for i, ev in enumerate(tag.events)), reverse=True)
    for p, _, ev in placed:
        s = f"{s[:p]} <{ev.tag}> {s[p:]}"
    s = re.sub(r"\s+", " ", s).strip()
    for word in tag.emphasis:
        s = re.sub(rf"(?<![\w(<>])({re.escape(word)})(?![\w)<>])", r"(((\1)))", s, count=1)
    if tag.emotion != "neutral" and tag.intensity >= KITTEN_MIN_INTENSITY:
        s = f"[{tag.emotion}] {s}"
    return s


def chatterbox_params(tag: EmotionTag) -> dict[str, float]:
    exaggeration = 0.5
    if tag.emotion in _HIGH_AROUSAL:
        exaggeration = 0.5 + 0.4 * tag.intensity
    elif tag.emotion in _LOW_AROUSAL:
        exaggeration = 0.5 - 0.2 * tag.intensity
    exaggeration = round(exaggeration, 3)
    return {"exaggeration": exaggeration, "cfg_weight": 0.3 if exaggeration > 0.7 else 0.5}


def render_request(engine: str, text: str, tag: EmotionTag) -> tuple[str, dict]:
    if engine == "kitten":
        return render_kitten(text, tag), {}
    if engine == "chatterbox":
        return text, chatterbox_params(tag)
    if engine in ("xtts", "fake"):
        return text, {}
    raise ValueError(f"Unbekannte Engine: {engine}")
