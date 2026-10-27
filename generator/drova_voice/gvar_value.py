"""Neutrale Fassung für Zeilen mit Quest- oder Geldwerten: "$GVAR:…Preis$ Münzen" -> "ein paar Münzen".

Die Mod kennt die Werte nicht. Gesprochen wird deshalb eine feste, ungenaue Menge; der Untertitel zeigt
weiter die echte Zahl. Ersetzt wird nur, was sicher grammatisch bleibt, alles andere bleibt stumm.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from drova_voice.player_name import NAME_TOKEN, NAME_VAR, make_name_variants
from drova_voice.speech_text import GVAR_RE, STAGE_RE


class Kind(StrEnum):
    CURRENCY = "currency"  # Wert vor einer Geldangabe ("… Münzen", "… Gold")
    COUNT = "count"  # Wert vor einem gezählten Nomen ("… Runden", "… Teilnehmer")
    BARE = "bare"  # Mengenvariable ohne bekanntes Nomen danach ("Das macht …."), bleibt stumm
    NAME = "name"  # anderer Name als der des Spielers, bleibt stumm
    UNKNOWN = "unknown"  # Variable ist nicht als Menge erkennbar, bleibt stumm


# Teilwörter im letzten Teil des Variablennamens (nach dem Punkt), klein geschrieben.
_QUANTITY_WORDS = (
    "preis",
    "price",
    "cost",
    "kosten",
    "gold",
    "geld",
    "money",
    "lohn",
    "reward",
    "belohnung",
    "fee",
    "gebühr",
    "betrag",
    "summe",
    "amount",
    "anzahl",
    "count",
    "menge",
    "number",
    "runden",
    "rounds",
    "participants",
    "teilnehmer",
)

# Nomen direkt nach dem Platzhalter -> (Mengenwort, Klasse). Nur Mehrzahl- und Stoffformen: "1 Münze"
# bleibt stumm, weil "ein paar Münze" falsch wäre. Dativformen stehen einzeln, das Nomen bleibt wie geschrieben.
TEMPLATES: dict[str, tuple[str, Kind]] = {
    "Münzen": ("ein paar", Kind.CURRENCY),
    "Goldmünzen": ("ein paar", Kind.CURRENCY),
    "Silbermünzen": ("ein paar", Kind.CURRENCY),
    "Kupfermünzen": ("ein paar", Kind.CURRENCY),
    "Goldstücke": ("ein paar", Kind.CURRENCY),
    "Goldstücken": ("ein paar", Kind.CURRENCY),
    "Gold": ("etwas", Kind.CURRENCY),
    "Silber": ("etwas", Kind.CURRENCY),
    "Runden": ("ein paar", Kind.COUNT),
    "Teilnehmer": ("ein paar", Kind.COUNT),
    "Teilnehmern": ("ein paar", Kind.COUNT),
    "Kämpfer": ("ein paar", Kind.COUNT),
    "Kämpfern": ("ein paar", Kind.COUNT),
    "Gegner": ("ein paar", Kind.COUNT),
    "Gegnern": ("ein paar", Kind.COUNT),
}

# Wörter vor dem Platzhalter, nach denen "ein paar" falsch klingt ("die ein paar Münzen", "etwa ein paar").
_BLOCKED_BEFORE = re.compile(
    r"(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer|eines"
    r"|(?:kein|mein|dein|sein|ihr|unser|dies|jen|solch|welch|all)(?:e|en|em|er|es)?"
    r"|eu(?:er|re|ren|rem|rer|res)|beide|viele|wenige|einige|mehrere|paar"
    r"|etwa|ungefähr|circa|ca|rund|knapp|genau|exakt|\d+)",
    re.IGNORECASE,
)
_NOUN_AFTER = re.compile(r"\s+(\w+)(?![\w-])")
_WORD_BEFORE = re.compile(r"(\w+)\s*$")
_SENTENCE_START = re.compile(r"(?:^|[.!?…])\s*(?:<br\s*/?>\s*)*$", re.IGNORECASE)


@dataclass(frozen=True)
class GvarValueResult:
    kind: Kind  # Musterklasse der Zeile (bei mehreren Werten die erste stumme, sonst die erste)
    neutral: str | None  # Text mit neutraler Menge (und ohne Spielernamen); None = bleibt stumm
    player_name: bool = False


def variable_kind(name: str) -> Kind:
    """BARE heißt hier: eine Mengenvariable. Erst das Nomen danach macht daraus currency oder count."""
    leaf = name.rpartition(".")[2].lower()
    if "name" in leaf:
        return Kind.NAME
    if any(word in leaf for word in _QUANTITY_WORDS):
        return Kind.BARE
    return Kind.UNKNOWN


def _replacement(text: str, m: re.Match) -> tuple[Kind, str | None]:
    kind = variable_kind(m.group(1))
    if kind is not Kind.BARE:
        return kind, None
    after = _NOUN_AFTER.match(text, m.end())
    template = TEMPLATES.get(after.group(1)) if after else None
    if template is None:
        return Kind.BARE, None
    quantity, kind = template
    before = text[: m.start()]
    word = _WORD_BEFORE.search(before)
    if word and _BLOCKED_BEFORE.fullmatch(word.group(1)):
        return kind, None
    if _SENTENCE_START.search(STAGE_RE.sub("", before)):
        quantity = quantity[0].upper() + quantity[1:]
    return kind, quantity


def neutralize_values(text: str) -> GvarValueResult | None:
    """None, wenn der Text keinen Quest- oder Geldwert enthält (kein Fall für dieses Modul)."""
    matches = [m for m in GVAR_RE.finditer(text) if m.group(1) != NAME_VAR]
    if not matches:
        return None
    has_name = NAME_TOKEN in text
    kinds: list[Kind] = []
    parts: list[str] = []
    last = 0
    failed: Kind | None = None
    for m in matches:
        kind, quantity = _replacement(text, m)
        kinds.append(kind)
        if quantity is None:
            failed = failed or kind
            continue
        parts += [text[last : m.start()], quantity]
        last = m.end()
    if failed is not None:
        return GvarValueResult(failed, None, has_name)
    result = "".join(parts) + text[last:]
    if has_name:
        neutral = make_name_variants(result).neutral
        return GvarValueResult(kinds[0], neutral, True)
    return GvarValueResult(kinds[0], result, False)


@dataclass
class Inventory:
    """Zählung je Musterklasse für den Bericht auf dem Rechner mit Spieldaten."""

    voiced: Counter
    silent: Counter
    with_name: Counter  # (Klasse, gesprochen?) für Zeilen, die zusätzlich den Spielernamen haben
    silent_vars: Counter  # (Variable, Klasse, Wort danach) der stummen Platzhalter

    @property
    def total(self) -> int:
        return sum(self.voiced.values()) + sum(self.silent.values())


def build_inventory(rows: Iterable[tuple[str, bool]]) -> Inventory:
    """rows: (Originaltext, gesprochen?) je Zeile mit Quest- oder Geldwert."""
    inv = Inventory(Counter(), Counter(), Counter(), Counter())
    for raw, spoken in rows:
        result = neutralize_values(raw)
        if result is None:
            continue
        (inv.voiced if spoken else inv.silent)[result.kind] += 1
        if result.player_name:
            inv.with_name[(result.kind, spoken)] += 1
        if spoken:
            continue
        for m in GVAR_RE.finditer(raw):
            if m.group(1) == NAME_VAR:
                continue
            kind, quantity = _replacement(raw, m)
            if quantity is None:
                after = _NOUN_AFTER.match(raw, m.end())
                inv.silent_vars[(m.group(1), kind, after.group(1) if after else "")] += 1
    return inv


def format_inventory(inv: Inventory, limit: int = 30) -> str:
    if not inv.total:
        return "keine Zeilen mit Quest- oder Geldwerten"
    voiced, silent = sum(inv.voiced.values()), sum(inv.silent.values())
    out = [f"Zeilen mit Quest- oder Geldwerten: {inv.total} (gesprochen {voiced}, stumm {silent})"]
    for kind in Kind:
        voiced, silent = inv.voiced[kind], inv.silent[kind]
        if voiced or silent:
            name = sum(n for (k, _), n in inv.with_name.items() if k is kind)
            extra = f"; davon mit Spielername {name}" if name else ""
            out.append(f"  {kind}: gesprochen {voiced}, stumm {silent}{extra}")
    if inv.silent_vars:
        out.append("stumme Platzhalter (Variable, Klasse, Wort danach):")
        for (var, kind, word), n in inv.silent_vars.most_common(limit):
            out.append(f"  {n}x {var} [{kind}] vor „{word}“" if word else f"  {n}x {var} [{kind}]")
        rest = len(inv.silent_vars) - limit
        if rest > 0:
            out.append(f"  … {rest} weitere")
    return "\n".join(out)
