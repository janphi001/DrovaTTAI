from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from drova_voice.export_report import loca_path_of
from drova_voice.ids import VARIANT_SEP, choice_id, normalize_loca_path, statement_id, with_variant
from drova_voice.jsonl import read_jsonl, write_jsonl
from drova_voice.loc import read_loc_file
from drova_voice.player_name import NAME_VAR, make_name_variants
from drova_voice.speech_text import GVAR_RE, Lexicon, build_speech_text, compile_lexicon

SKIP_GVAR_NAME = "gvar_name"  # nur der Spielername, aber keine neutrale Fassung ohne ihn
SKIP_GVAR_VALUE = (
    "gvar_value"  # Quest- oder Geldwerte (oder Name zusammen mit Werten): nicht vorab vertonbar
)
NEUTRAL = "neutral"
SKIP_UNSPEAKABLE = "unspeakable"
SKIP_ID_MISMATCH = "id_mismatch"
SKIP_PLAYER_CHOICE = (
    "player_choice"  # Auswahloptionen spricht das Spiel nicht; der Spieler bleibt dort stumm
)


@dataclass(frozen=True)
class Line:
    id: str
    tree: str
    loca_path: str
    loca_key: str
    node_type: str
    choice_index: int | None
    actor: str
    category: str
    generic: bool
    raw: str  # Text der .loc (oder des Manifests), noch mit Regieanweisungen und Platzhaltern
    speech: str  # Sprechtext, leer bei übersprungenen Zeilen
    stage: tuple[dict, ...] = ()  # [{"text": "seufzt", "pos": 0}], pos = Zeichenindex im Sprechtext
    skip: str | None = None
    pool: str | None = None  # Poolstimme (vm1, vw2 …) bei erweiterten Zeilen generischer Sprecher

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Line:
        return cls(**{**d, "stage": tuple(d.get("stage", ()))})


def emotion_id(line: Line) -> str:
    """Schlüssel in casting/emotions.jsonl: Poolzeilen teilen die Emotion ihrer Basiszeile."""
    return line.id.rpartition(VARIANT_SEP)[0] if line.pool else line.id


def load_loc_texts(loc_dir: Path, language: str) -> dict[tuple[str, str], str]:
    texts: dict[tuple[str, str], str] = {}
    loc_dir = Path(loc_dir)
    for file in sorted(loc_dir.rglob("*.loc")):
        path = loca_path_of(file, loc_dir, language)
        for entry in read_loc_file(file).entries:
            texts[(path, entry.key)] = entry.text
    return texts


def load_lexicon(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Lexikon muss aus 'Wort: Aussprache'-Zeilen bestehen")
    mapping = {str(k): str(v) for k, v in raw.items()}
    try:
        compile_lexicon(mapping)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None
    return mapping


def _expected_id(row: Mapping) -> str:
    if row.get("nodeType") == "choice":
        return choice_id(row["tree"], row["locaPath"], row["locaKey"], row["choiceIndex"])
    return statement_id(row["tree"], row["locaPath"], row["locaKey"])


def build_lines(
    manifest: Mapping,
    loc_texts: Mapping[tuple[str, str], str],
    lexicon: Mapping[str, str] | None = None,
    language: str = "de",
) -> list[Line]:
    built = compile_lexicon(lexicon or {})
    compiled: Lexicon | None = built if built.pattern is not None else None
    seen: set[tuple[str, bool]] = set()
    out: list[tuple[str, Line]] = []
    for row in manifest.get("lines", []):
        line_id = row["id"]
        try:
            id_ok = _expected_id(row) == line_id
        except (KeyError, TypeError, ValueError):
            id_ok = False
        if (line_id, id_ok) in seen:  # gleiche Bäume können mehrfach im Speicher liegen
            continue
        seen.add((line_id, id_ok))
        path = normalize_loca_path(row["locaPath"])
        raw = loc_texts.get((path, row["locaKey"]), row.get("text") or "")
        speech, skip = "", None
        stage: tuple[dict, ...] = ()
        out_id = line_id
        if not id_ok:
            skip = SKIP_ID_MISMATCH
        elif row.get("nodeType") == "choice":
            skip = SKIP_PLAYER_CHOICE
        elif "$GVAR:" in raw:
            if set(GVAR_RE.findall(raw)) != {NAME_VAR}:
                skip = SKIP_GVAR_VALUE
            else:
                neutral = make_name_variants(raw).neutral
                st = (
                    build_speech_text(neutral, None, compiled, language)
                    if neutral is not None
                    else None
                )
                if st is None:
                    skip = SKIP_GVAR_NAME
                elif st.is_speakable:
                    speech, stage = st.text, tuple({"text": s.text, "pos": s.pos} for s in st.stage)
                    out_id = with_variant(line_id, NEUTRAL)
                else:
                    skip = SKIP_UNSPEAKABLE
        else:
            st = build_speech_text(raw, None, compiled, language)
            if st.is_speakable:
                speech, stage = st.text, tuple({"text": s.text, "pos": s.pos} for s in st.stage)
            else:
                skip = SKIP_UNSPEAKABLE
        out.append(
            (
                line_id,
                Line(
                    id=out_id,
                    tree=row["tree"],
                    loca_path=path,
                    loca_key=row["locaKey"],
                    node_type=row["nodeType"],
                    choice_index=row.get("choiceIndex"),
                    actor=row.get("actorName") or "",
                    category=row.get("category") or "dialog",
                    generic=bool(row.get("generic")),
                    raw=raw,
                    speech=speech,
                    stage=stage,
                    skip=skip,
                ),
            )
        )
    valid_ids = {base for base, l in out if l.skip != SKIP_ID_MISMATCH}
    return [
        l for base, l in out if not (l.skip == SKIP_ID_MISMATCH and base in valid_ids)
    ]  # gültige Zeile geht vor


def select_npc(lines: Sequence[Line], npc: str) -> list[Line]:
    """Alle Zeilen der Bäume, in denen der NPC spricht (Spieler-Auswahloptionen derselben Bäume sind dabei, werden aber als `player_choice` übersprungen)."""
    wanted = npc.lower()
    trees = {l.tree for l in lines if l.actor.lower() == wanted}
    return [l for l in lines if l.tree in trees]


def write_lines(path: Path, lines: Sequence[Line]) -> None:
    write_jsonl(path, (l.to_dict() for l in lines))


def read_lines(path: Path) -> list[Line]:
    return [Line.from_dict(d) for d in read_jsonl(path)]
