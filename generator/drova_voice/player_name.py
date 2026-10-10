from __future__ import annotations

import re
from dataclasses import dataclass

NAME_TOKEN = "$GVAR:EVars_Player.Name$"
DEFAULT_NAME = "Arden"

GREETINGS = ("Hallo", "Hey", "Hi", "Na", "Ah", "Oh", "Danke", "Willkommen", "Moin", "Tag", "Servus", "Grüß dich")

_N = re.escape(NAME_TOKEN)
# Artikel und Possessivdeterminierer, die einen Appositiv einleiten ("NAME, der Vogt, ...").
_DETERMINERS = (
    r"(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer)\b"
    r"|(?:mein|dein|sein|ihr|unser|euer)\w*"
)
_RULES: list[tuple[re.Pattern, object]] = [
    # "Danke, NAME." / "Wir gehen zum Wald, NAME ..."
    (re.compile(rf",\s*{_N}(?=\s*(?:\.\.\.|…|[.!?]|$))"), ""),
    # "NAME, komm her." am Satzanfang – nicht bei Appositiven ("NAME, der Vogt, ...")
    (re.compile(rf"(?:^|(?<=[.!?…]\s)){_N}\s*,\s*(?!(?i:{_DETERMINERS}))(\w)"), lambda m: m.group(1).upper()),
    # "Lanzo! NAME!" – Name als eigener Ausruf nach Satzende
    (re.compile(rf"(?<=[.!?…]\s){_N}\s*[.!?](?![.!?…])\s*"), ""),
    # "Hallo NAME!" / "Hallo NAME, ..."
    (re.compile(rf"\b({'|'.join(map(re.escape, GREETINGS))})\s+{_N}(?=\s*[,.!?…])"), r"\1"),
]


@dataclass(frozen=True)
class NameVariants:
    arden: str
    neutral: str | None

    @property
    def needs_review(self) -> bool:
        return self.neutral is None


def has_player_name(text: str) -> bool:
    return NAME_TOKEN in text


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.!?](?!\.))", r"\1", text)
    return text.strip()


def _neutralize(text: str) -> str | None:
    result = text
    for pattern, repl in _RULES:
        result = pattern.sub(repl, result)
    if NAME_TOKEN in result:
        return None
    result = _tidy(result)
    if not any(ch.isalnum() for ch in result):
        return None
    return result


def make_name_variants(text: str) -> NameVariants:
    return NameVariants(arden=text.replace(NAME_TOKEN, DEFAULT_NAME), neutral=_neutralize(text))
