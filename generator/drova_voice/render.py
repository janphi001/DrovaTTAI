from __future__ import annotations

import re

from drova_voice.emotions import EmotionTag

KITTEN_MIN_INTENSITY = 0.3
_HIGH_AROUSAL = {"angry", "excited", "surprised", "joyful", "stern"}
_LOW_AROUSAL = {"sad", "tender", "contemplative", "mundane"}

FISH_MIN_INTENSITY = 0.3
FISH_STRONG_INTENSITY = 0.8
# Emotionsname im Projekt -> Fish-Cue (englisch, frei formulierbar; nur Cues, die im Hörtest verwendet wurden).
_FISH_CUES = {
    "angry": "angry", "sad": "sad", "joyful": "happy", "stern": "stern", "excited": "excited",
    "nervous": "nervous", "tender": "tender", "surprised": "surprised", "contemplative": "thoughtful",
}
# Laute, deren Wirkung geprüft ist; andere Ereignisse werden weggelassen.
_FISH_EVENTS = {"sigh": "[sighing]", "laugh": "[laughing]", "pause": "[break]"}


def render_fish(text: str, tag: EmotionTag) -> str:
    s = text
    n = len(text)
    placed = sorted(
        ((max(0, min(ev.pos, n)), i, ev) for i, ev in enumerate(tag.events) if ev.tag in _FISH_EVENTS), reverse=True
    )
    for p, _, ev in placed:
        s = f"{s[:p]} {_FISH_EVENTS[ev.tag]} {s[p:]}"
    s = re.sub(r"\s+", " ", s).strip()
    for word in tag.emphasis:
        s = re.sub(rf"(?<![\w\[\]])({re.escape(word)})(?![\w\[\]])", r"[emphasis] \1", s, count=1)
    cue = _FISH_CUES.get(tag.emotion)
    if cue and tag.intensity >= FISH_MIN_INTENSITY:
        s = f"[{'very ' + cue if tag.intensity >= FISH_STRONG_INTENSITY else cue}] {s}"
    return s


def render_kitten(text: str, tag: EmotionTag) -> str:
    # Laut-Tags (<sigh>, <laugh> ...) werden bewusst nicht gerendert: Kitten spricht sie auf Deutsch laut aus
    # (Hörtest 2026-10-10). Emotion und Betonung wirken, wenn auch nur schwach.
    s = re.sub(r"\s+", " ", text).strip()
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
    # Letzte Schutzschicht: ein Text ohne Buchstaben oder Ziffern erzeugt nur Stille oder Müll in der Engine.
    if not any(ch.isalnum() for ch in text):
        raise ValueError("Text ist nicht sprechbar: er enthält keine Buchstaben oder Ziffern")
    if engine == "kitten":
        rendered = render_kitten(text, tag)
        # Tags (Emotion, Laute) wirken nur im Preset "expressive"; "stable" dämpft sie.
        return rendered, ({"preset": "expressive"} if rendered != render_kitten(text, EmotionTag()) else {})
    if engine == "chatterbox":
        return text, chatterbox_params(tag)
    if engine in ("xtts", "fake"):
        return text, {}
    if engine == "fish":
        return render_fish(text, tag), {}
    raise ValueError(f"Unbekannte Engine: {engine}")
