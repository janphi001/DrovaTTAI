from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from drova_voice.bakeoff import (REF_TEXT, BakeoffResult, Sample, VoiceSpec, load_voice_specs,
                                 run_bakeoff, select_samples, write_sheet)
from drova_voice.config import DEFAULT_CONFIG_PATH, load_config
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineClient, EngineError, cache_env, worker_command
from drova_voice.engines.protocol import SynthRequest
from drova_voice.export_report import compute_coverage, format_report
from drova_voice.jsonl import read_jsonl, replace_with_retry, write_jsonl
from drova_voice.render import render_request

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
DEFAULT_VOICES = Path(__file__).resolve().parents[1] / "bakeoff_voices.yaml"


CACHE_DIR = WORKERS_DIR.parents[1] / "cache"


def _client(engine: str) -> EngineClient:
    return EngineClient(worker_command(WORKERS_DIR, engine), env=cache_env(CACHE_DIR))


def _merge_results(path: Path, new: list[BakeoffResult]) -> list[BakeoffResult]:
    merged = {}
    if path.exists():
        for d in read_jsonl(path):
            r = BakeoffResult.from_dict(d)
            merged[(r.engine, r.voice_slug, r.sample_id)] = r
    for r in new:
        old = merged.get((r.engine, r.voice_slug, r.sample_id))
        if r.seconds == 0.0 and old is not None and old.ok:
            continue  # übersprungene Datei: gemessene Werte behalten
        merged[(r.engine, r.voice_slug, r.sample_id)] = r
    results = list(merged.values())
    write_jsonl(path, (r.to_dict() for r in results))
    return results


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="drova-voice")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    sub = p.add_subparsers(dest="cmd", required=True)
    bake = sub.add_parser("bakeoff", help="TTS-Hörtest").add_subparsers(dest="bcmd", required=True)
    sel = bake.add_parser("select", help="Stichprobe aus den .loc-Dateien ziehen")
    sel.add_argument("--per-bucket", type=int, default=4)
    run = bake.add_parser("run", help="Stichprobe mit allen Stimmen erzeugen")
    run.add_argument("--voices", type=Path, default=DEFAULT_VOICES)
    run.add_argument("--engine", action="append", help="nur diese Engine(s)")
    bake.add_parser("sheet", help="Hörseite neu schreiben")
    refs = bake.add_parser("refs", help="Referenzstimmen mit XTTS-Sprechern erzeugen")
    refs.add_argument("--speaker", action="append", required=True)
    smoke = sub.add_parser("smoke", help="Engine mit einem Testsatz prüfen")
    smoke.add_argument("engine")
    exp = sub.add_parser("export", help="Export-Ergebnis der Mod prüfen").add_subparsers(dest="ecmd", required=True)
    rep = exp.add_parser("report", help="Abdeckung des Manifests gegen die .loc-Dateien")
    rep.add_argument("--manifest", type=Path)
    rep.add_argument("--min-coverage", type=float, default=98.0)
    exp.add_parser("fetch", help="Export-Ordner aus dem Spielordner nach data/export kopieren")
    return p.parse_args(argv)


def _run(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"FEHLER: Konfigurationsdatei nicht gefunden: {args.config}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"FEHLER: Konfigurationsdatei nicht lesbar: {args.config} ({e.strerror or e})", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2
    bake_data = cfg.data_dir / "bakeoff"
    bake_out = cfg.out_dir / "bakeoff"
    samples_path = bake_data / "samples.jsonl"
    results_path = bake_out / "results.jsonl"

    if args.cmd == "smoke":
        out = cfg.out_dir / "smoke" / f"{args.engine}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        with _client(args.engine) as client:  # zuerst: unbekannte Engine -> EngineError
            text, params = render_request(args.engine, "Hallo, ich bin ein Test der Sprachausgabe.", EmotionTag())
            resp = client.synth(SynthRequest(id="smoke", text=text, out_path=str(out), params=params))
        print(f"{args.engine}: {'OK' if resp.ok else 'FEHLER'} {resp.duration or ''} {resp.error or ''} -> {out}")
        return 0 if resp.ok else 1

    if args.cmd == "export":
        export_dir = cfg.data_dir / "export" / cfg.language
        if args.ecmd == "fetch":
            src = cfg.game_dir / "Mods" / "DrovaVoice" / "Export" / cfg.language
            if not src.is_dir():
                print(f"FEHLER: Export-Ordner nicht gefunden: {src} (Export im Spiel auslösen, siehe docs/export.md)", file=sys.stderr)
                return 2
            export_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, export_dir, dirs_exist_ok=True)
            print(f"{src} -> {export_dir}")
            return 0
        manifest_path = args.manifest or (export_dir / "manifest.json")
        if not manifest_path.is_file():
            print(f"FEHLER: Manifest nicht gefunden: {manifest_path} (Export im Spiel auslösen, siehe docs/export.md)", file=sys.stderr)
            return 2
        cov = compute_coverage(json.loads(manifest_path.read_text(encoding="utf-8-sig")), cfg.loc_dir, cfg.language)
        missing_path = manifest_path.with_name("coverage_missing.txt")
        missing_path.write_text("".join(f"{m}\n" for m in cov.missing), encoding="utf-8")
        print(format_report(cov, missing_path))
        return 0 if cov.percent >= args.min_coverage else 1

    if args.bcmd == "select":
        try:
            samples = select_samples(cfg.loc_dir, per_bucket=args.per_bucket)
        except (FileNotFoundError, ValueError) as e:  # alte samples.jsonl bleibt dabei unangetastet
            print(f"FEHLER: {e}", file=sys.stderr)
            return 2
        write_jsonl(samples_path, (s.to_dict() for s in samples))
        print(f"{len(samples)} Zeilen -> {samples_path}")
        return 0

    if args.bcmd == "refs":
        target = cfg.voices_dir / "bakeoff"
        target.mkdir(parents=True, exist_ok=True)
        failed_refs = 0
        with _client("xtts") as client:
            for speaker in args.speaker:
                slug = VoiceSpec("xtts", voice=speaker).slug
                out = target / f"xtts-{slug}.wav"
                part = out.with_name(f"xtts-{slug}.part.wav")
                resp = client.synth(SynthRequest(id=slug, text=REF_TEXT, out_path=str(part), voice=speaker))
                if resp.ok:
                    # Kitten braucht den gesprochenen Text zum Klonen (sonst lädt es Whisper, nur Englisch).
                    out.with_suffix(".txt").write_text(REF_TEXT, encoding="utf-8")
                    replace_with_retry(part, out)
                else:
                    part.unlink(missing_ok=True)
                    failed_refs += 1
                print(f"{speaker}: {'OK' if resp.ok else resp.error} -> {out}")
        return 1 if failed_refs else 0

    samples = [Sample.from_dict(d) for d in read_jsonl(samples_path)]

    if args.bcmd == "run":
        voices = load_voice_specs(args.voices, cfg.repo_root)
        if args.engine:
            voices = [v for v in voices if v.engine in args.engine]
            if not voices:
                print(f"FEHLER: keine Stimme für Engine(s) {', '.join(args.engine)} in {args.voices}", file=sys.stderr)
                return 2

        missing = []
        for v in voices:
            if v.reference and not Path(v.reference).is_file():
                missing.append(f"Referenz fehlt: {v.reference} (erzeugen mit `drova-voice bakeoff refs --speaker ...`)")
            elif v.reference and v.engine == "kitten" and not Path(v.reference).with_suffix(".txt").is_file():
                missing.append(f"Referenztext fehlt: {Path(v.reference).with_suffix('.txt')} (Kitten braucht den gesprochenen Text zum Klonen)")
        if missing:
            for line in missing:
                print(f"FEHLER: {line}", file=sys.stderr)
            return 2

        def persist(r: BakeoffResult) -> None:
            try:
                _merge_results(results_path, [r])  # sofort sichern, damit ein Abbruch nichts verliert
            except OSError as e:  # z. B. Datei kurz gesperrt: der Endabgleich holt es nach
                print(f"WARNUNG: Zwischenstand nicht gesichert: {e}", file=sys.stderr)

        new = run_bakeoff(samples, voices, _client, bake_out, on_result=persist)
        results = _merge_results(results_path, new)
        failed = [r for r in new if not r.ok]
        for r in failed:
            print(f"FEHLER {r.engine}/{r.voice_slug}/{r.sample_id}: {r.error}", file=sys.stderr)
    else:  # sheet
        results = [BakeoffResult.from_dict(d) for d in read_jsonl(results_path)] if results_path.exists() else []

    page = write_sheet(samples, results, bake_out)
    print(f"Hörseite: {page}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows-Konsolen (cp1252) dürfen beim Ausgeben von Pfaden nicht abstürzen.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = _parse(argv)
    try:
        return _run(args)
    except EngineError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
