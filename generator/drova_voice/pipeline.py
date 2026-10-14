from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

from drova_voice.casting import cast_report, load_casting
from drova_voice.config import Config
from drova_voice.emote import merge_emotions, read_emotions, write_emotions
from drova_voice.fish_voices import load_fish_voices
from drova_voice.lines import (Line, build_lines, load_lexicon, load_loc_texts, read_lines, select_npc, write_lines)

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"


def _fail(message: str) -> int:
    print(f"FEHLER: {message}", file=sys.stderr)
    return 2


def lines_path(cfg: Config) -> Path:
    return cfg.data_dir / "lines.jsonl"


def _selected(cfg: Config, args: argparse.Namespace) -> list[Line] | None:
    """Zeilen aus data/lines.jsonl, bei --npc gefiltert; None (mit Meldung), wenn extract noch nicht lief."""
    path = lines_path(cfg)
    if not path.is_file():
        _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
        return None
    lines = read_lines(path)
    npc = getattr(args, "npc", None)
    if npc:
        lines = select_npc(lines, npc)
        if not lines:
            _fail(f"Keine Zeilen für NPC '{npc}' gefunden")
            return None
    return lines


def _extract(cfg: Config, args: argparse.Namespace) -> int:
    manifest_path = args.manifest or (cfg.data_dir / "export" / cfg.language / "manifest.json")
    if not Path(manifest_path).is_file():
        return _fail(f"Manifest nicht gefunden: {manifest_path} (Export im Spiel auslösen, siehe docs/export.md)")
    if not cfg.loc_dir.is_dir():
        return _fail(f"Lokalisierungsordner nicht gefunden: {cfg.loc_dir} (game_dir in config.yaml prüfen)")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    lexicon = load_lexicon(cfg.casting_dir / "lexicon.yaml")
    lines = build_lines(manifest, load_loc_texts(cfg.loc_dir, cfg.language), lexicon)
    write_lines(lines_path(cfg), lines)
    skips = Counter(l.skip for l in lines if l.skip)
    detail = ", ".join(f"{reason}: {n}" for reason, n in sorted(skips.items())) or "keine"
    print(f"{len(lines)} Zeilen -> {lines_path(cfg)}; übersprungen: {detail}")
    return 0


def _load_casting(cfg: Config):
    voices = load_fish_voices(cfg.casting_dir / "fish_voices.yaml")
    return voices, load_casting(cfg.casting_dir / "casting.yaml", voices)


def _cast(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        _, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    report = cast_report(lines, casting)
    print("Stimmen (Zeilen): " + (", ".join(f"{v}: {n}" for v, n in sorted(report.usage.items())) or "keine"))
    print("Sprecher ohne Stimme: " + (", ".join(f"{a}: {n}" for a, n in sorted(report.missing.items())) or "keine"))
    return 1 if report.missing else 0


def emotions_path(cfg: Config) -> Path:
    return cfg.casting_dir / "emotions.jsonl"


def _emote(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        merged = merge_emotions(read_emotions(emotions_path(cfg)), lines)
    except ValueError as e:
        return _fail(str(e))
    write_emotions(emotions_path(cfg), merged)
    sources = Counter(t.source for t in merged.values())
    print(f"{len(merged)} Emotionen -> {emotions_path(cfg)}; " + ", ".join(f"{s}: {n}" for s, n in sorted(sources.items())))
    return 0


HANDLERS: dict[str, Callable[[Config, argparse.Namespace], int]] = {
    "extract": _extract,
    "cast": _cast,
    "emote": _emote,
}


def add_parsers(sub) -> None:
    ex = sub.add_parser("extract", help="Manifest + .loc -> data/lines.jsonl (Sprechtext)")
    ex.add_argument("--manifest", type=Path, help="Standard: data/export/<Sprache>/manifest.json")
    cast = sub.add_parser("cast", help="Prüft, ob jeder Sprecher eine Stimme hat (casting/casting.yaml)")
    cast.add_argument("--check", action="store_true", help="nur prüfen (Standard und einzige Betriebsart in Plan 3)")
    cast.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    em = sub.add_parser("emote", help="Emotionen aus Regieanweisungen nach casting/emotions.jsonl (llm/manual bleiben)")
    em.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
