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
from drova_voice.encode import run_encode
from drova_voice.engines.client import EngineClient, cache_env, worker_command
from drova_voice.fish_voices import load_fish_voices
from drova_voice.install import install_audio
from drova_voice.jsonl import append_jsonl, latest_by_id, read_jsonl_lenient, write_jsonl
from drova_voice.lines import (Line, build_lines, load_lexicon, load_loc_texts, read_lines, select_npc, write_lines)
from drova_voice.preview import write_preview
from drova_voice.report import build_report, format_report
from drova_voice.synth import build_jobs, run_synth

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


def synth_results_path(cfg: Config) -> Path:
    return cfg.data_dir / "synth" / "results.jsonl"


def _client_factory(cfg: Config):
    def make(engine: str) -> EngineClient:
        return EngineClient(worker_command(WORKERS_DIR, engine), env=cache_env(cfg.cache_dir))
    return make


def _synth(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        voices, casting = _load_casting(cfg)
        emotions = read_emotions(emotions_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    jobs, skipped = build_jobs(lines, casting, voices, emotions, args.engine)
    if args.limit:
        jobs = jobs[: args.limit]
    cache_dir = cfg.cache_dir / "synth"
    path = synth_results_path(cfg)
    results = run_synth(jobs, args.engine, _client_factory(cfg), cache_dir, args.workers,
                        on_result=lambda r: append_jsonl(path, r.to_dict()))
    done = [r for r in results if r.ok]
    new = [r for r in done if r.attempts > 0]
    failed = [r for r in results if not r.ok]
    flagged = [r for r in done if r.flagged]
    reasons = Counter(skipped.values())
    detail = ", ".join(f"{k}: {n}" for k, n in sorted(reasons.items())) or "keine"
    print(f"{len(done)} erzeugt ({len(done) - len(new)} aus dem Cache, {len(new)} neu erzeugt), {len(failed)} Fehler, "
          f"{len(flagged)} auffällige Dauer; übersprungen: {detail}")
    for r in failed[:10]:
        print(f"FEHLER {r.id}: {r.error}", file=sys.stderr)
    for r in flagged[:10]:
        print(f"AUFFÄLLIG {r.id}: Dauer {r.duration:.1f} s", file=sys.stderr)
    return 1 if failed else 0


def encoded_path(cfg: Config) -> Path:
    return cfg.data_dir / "encoded.jsonl"


def audio_dir(cfg: Config) -> Path:
    return cfg.out_dir / "audio" / cfg.language


def _encode(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    synth_rows = latest_by_id(read_jsonl_lenient(synth_results_path(cfg)))
    if not synth_rows:
        return _fail(f"{synth_results_path(cfg)} fehlt oder ist leer (zuerst `drova-voice synth` ausführen)")
    try:
        emotions = read_emotions(emotions_path(cfg))
        rows, errors = run_encode(lines, synth_rows, emotions, audio_dir(cfg), args.workers)
    except ValueError as e:
        return _fail(str(e))
    merged = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    merged.update({r["id"]: r for r in rows})
    write_jsonl(encoded_path(cfg), merged.values())
    print(f"{len(rows)} kodiert -> {audio_dir(cfg)}; {len(errors)} Fehler")
    for e in errors[:10]:
        print(f"FEHLER {e}", file=sys.stderr)
    return 1 if errors else 0


def _install(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    if not encoded:
        return _fail(f"{encoded_path(cfg)} fehlt oder ist leer (zuerst `drova-voice encode` ausführen)")
    wanted = {l.id for l in lines}
    rows = [r for i, r in encoded.items() if i in wanted]
    result = install_audio(rows, audio_dir(cfg), cfg.install_dir, cfg.language)
    print(f"{result.copied} Dateien kopiert, index.json mit {result.entries} Einträgen -> {cfg.install_dir}")
    for e in result.errors[:10]:
        print(f"FEHLER {e}", file=sys.stderr)
    return 1 if result.errors else 0


def _report(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        _, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    index_path = cfg.install_dir / "index.json"
    entries = {}
    if index_path.is_file():
        entries = json.loads(index_path.read_text(encoding="utf-8-sig")).get("entries", {})
    statuses = build_report(lines, casting, latest_by_id(read_jsonl_lenient(synth_results_path(cfg))),
                            latest_by_id(read_jsonl_lenient(encoded_path(cfg))), entries)
    print(format_report(statuses))
    return 0


def _preview(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        emotions = read_emotions(emotions_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    page = write_preview(lines, latest_by_id(read_jsonl_lenient(encoded_path(cfg))), emotions, audio_dir(cfg),
                         cfg.out_dir / "preview" / "index.html", f"Hörprobe {args.npc or 'alle Zeilen'}")
    print(f"Hörseite: {page}")
    return 0


HANDLERS: dict[str, Callable[[Config, argparse.Namespace], int]] = {
    "extract": _extract,
    "cast": _cast,
    "emote": _emote,
    "synth": _synth,
    "encode": _encode,
    "install": _install,
    "report": _report,
    "preview": _preview,
}


def add_parsers(sub) -> None:
    ex = sub.add_parser("extract", help="Manifest + .loc -> data/lines.jsonl (Sprechtext)")
    ex.add_argument("--manifest", type=Path, help="Standard: data/export/<Sprache>/manifest.json")
    cast = sub.add_parser("cast", help="Prüft, ob jeder Sprecher eine Stimme hat (casting/casting.yaml)")
    cast.add_argument("--check", action="store_true", help="nur prüfen (Standard und einzige Betriebsart in Plan 3)")
    cast.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    em = sub.add_parser("emote", help="Emotionen aus Regieanweisungen nach casting/emotions.jsonl (llm/manual bleiben)")
    em.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    sy = sub.add_parser("synth", help="Sprache erzeugen (Cache unter cache/synth, wiederaufnehmbar)")
    sy.add_argument("--engine", default="fish")
    sy.add_argument("--workers", type=int, default=8, help="parallele Anfragen (Standard 8, gemessen ohne 429 bis 16)")
    sy.add_argument("--limit", type=int, help="nur die ersten N Aufträge (zum Ausprobieren)")
    sy.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    en = sub.add_parser("encode", help="WAV -> OGG (Stille trimmen, -16 LUFS, mono) nach out/audio/<Sprache>")
    en.add_argument("--workers", type=int, default=4)
    en.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    ins = sub.add_parser("install", help="Dateien in den Mod-Ordner kopieren und index.json schreiben")
    ins.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht (frühere Einträge bleiben erhalten)")
    rp = sub.add_parser("report", help="Status je Kategorie: offen, erzeugt, kodiert, installiert, übersprungen")
    rp.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    pv = sub.add_parser("preview", help="Hörseite out/preview/index.html (Zeilen mit Emotion und Audio)")
    pv.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
