from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

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


def apply_lexicon(text: str, lexicon: Mapping[str, str]) -> str:
    for word, spoken in lexicon.items():
        text = re.sub(rf"\b{re.escape(word)}\b", spoken, text)
    return text


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
    lexicon: Mapping[str, str] | None = None,
) -> SpeechText:
    text, unresolved = substitute_gvars(raw, gvar_values or {})
    text = _replace_br(text)
    text = _TAG_RE.sub("", text)
    text = _numbers_to_words(text)
    if lexicon:
        text = apply_lexicon(text, lexicon)
    clean, stage = extract_stage_directions(text)
    return SpeechText(clean, stage, unresolved)
