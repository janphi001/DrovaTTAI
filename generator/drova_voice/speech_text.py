from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from num2words import num2words

STAGE_RE = re.compile(r"\*([^*\n]{1,300})\*")
GVAR_RE = re.compile(r"\$GVAR:([^$]+)\$")
_BR_RE = re.compile(r"\s*<br\s*/?>\s*", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_NUM_RE = re.compile(r"\b\d+\b")
_WS_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.!?…;:])")


@dataclass(frozen=True)
class StageDirection:
    text: str
    pos: int


@dataclass(frozen=True)
class Lexicon:
    """Einmal gebaute Wortliste. Die Aussprache wird nicht erneut durchsucht."""

    pattern: re.Pattern[str] | None
    spoken: Mapping[str, str]


@dataclass(frozen=True)
class SpeechText:
    text: str
    stage: tuple[StageDirection, ...] = ()
    unresolved_gvars: tuple[str, ...] = ()

    @property
    def is_speakable(self) -> bool:
        return any(ch.isalnum() for ch in self.text)


def substitute_gvars(text: str, values: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    unresolved: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in values:
            return str(values[name])
        unresolved.append(name)
        return ""

    return GVAR_RE.sub(repl, text), tuple(unresolved)


def _replace_br(text: str) -> str:
    def repl(m: re.Match) -> str:
        before = text[: m.start()].rstrip()
        return ". " if before and before[-1].isalnum() else " "

    return _BR_RE.sub(repl, text)


def _numbers_to_words(text: str) -> str:
    return _NUM_RE.sub(lambda m: num2words(int(m.group(0)), lang="de"), text)


def compile_lexicon(lexicon: Mapping[str, str]) -> Lexicon:
    items: list[tuple[str, str]] = []
    for key, spoken in lexicon.items():
        word = str(key)
        if word == "":
            raise ValueError("Lexikon-Schlüssel darf nicht leer sein")
        items.append((word, str(spoken)))
    if not items:
        return Lexicon(None, {})
    pattern = re.compile("|".join(rf"\b{re.escape(word)}\b" for word, _ in items))
    return Lexicon(pattern, dict(items))


def apply_lexicon(text: str, lexicon: Mapping[str, str] | Lexicon) -> str:
    compiled = lexicon if isinstance(lexicon, Lexicon) else compile_lexicon(lexicon)
    pattern = compiled.pattern
    if pattern is None:
        return text
    # Lambda statt Ersatztext: re wertet Backslashes im Ersatz sonst als Escapes aus.
    spoken = compiled.spoken
    return pattern.sub(lambda match: spoken[match.group(0)], text)


def _tidy(text: str) -> str:
    text = _WS_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return text.strip()


def extract_stage_directions(text: str) -> tuple[str, tuple[StageDirection, ...]]:
    parts: list[str] = []
    found: list[StageDirection] = []
    last = 0
    for m in STAGE_RE.finditer(text):
        parts.append(text[last : m.start()])
        last = m.end()
        found.append(StageDirection(m.group(1).strip(), len(_tidy("".join(parts)))))
    parts.append(text[last:])
    clean = _tidy("".join(parts))
    return clean, tuple(StageDirection(s.text, min(s.pos, len(clean))) for s in found)


def build_speech_text(
    raw: str,
    gvar_values: Mapping[str, str] | None = None,
    lexicon: Mapping[str, str] | Lexicon | None = None,
) -> SpeechText:
    text, unresolved = substitute_gvars(raw, gvar_values or {})
    text = _replace_br(text)
    text = _TAG_RE.sub("", text)
    text = _numbers_to_words(text)
    if lexicon:
        text = apply_lexicon(text, lexicon)
    clean, stage = extract_stage_directions(text)
    return SpeechText(clean, stage, unresolved)
