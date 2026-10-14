from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

from drova_voice.config import Config
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


HANDLERS: dict[str, Callable[[Config, argparse.Namespace], int]] = {
    "extract": _extract,
}


def add_parsers(sub) -> None:
    ex = sub.add_parser("extract", help="Manifest + .loc -> data/lines.jsonl (Sprechtext)")
    ex.add_argument("--manifest", type=Path, help="Standard: data/export/<Sprache>/manifest.json")
