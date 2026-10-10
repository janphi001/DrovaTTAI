from __future__ import annotations

import argparse
import sys
from pathlib import Path

from drova_voice.bakeoff import (REF_TEXT, BakeoffResult, Sample, VoiceSpec, load_voice_specs,
                                 run_bakeoff, select_samples, write_sheet)
from drova_voice.config import DEFAULT_CONFIG_PATH, load_config
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineClient, worker_command
from drova_voice.engines.protocol import SynthRequest
from drova_voice.jsonl import read_jsonl, write_jsonl
from drova_voice.render import render_request

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
DEFAULT_VOICES = Path(__file__).resolve().parents[1] / "bakeoff_voices.yaml"


def _client(engine: str) -> EngineClient:
    return EngineClient(worker_command(WORKERS_DIR, engine))


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


def main(argv: list[str] | None = None) -> int:
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
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    bake_data = cfg.data_dir / "bakeoff"
    bake_out = cfg.out_dir / "bakeoff"
    samples_path = bake_data / "samples.jsonl"
    results_path = bake_out / "results.jsonl"

    if args.cmd == "smoke":
        out = cfg.out_dir / "smoke" / f"{args.engine}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        text, params = render_request(args.engine, "Hallo, ich bin ein Test der Sprachausgabe.", EmotionTag())
        with _client(args.engine) as client:
            resp = client.synth(SynthRequest(id="smoke", text=text, out_path=str(out), params=params))
        print(f"{args.engine}: {'OK' if resp.ok else 'FEHLER'} {resp.duration or ''} {resp.error or ''} → {out}")
        return 0 if resp.ok else 1

    if args.bcmd == "select":
        samples = select_samples(cfg.loc_dir, per_bucket=args.per_bucket)
        write_jsonl(samples_path, (s.to_dict() for s in samples))
        print(f"{len(samples)} Zeilen → {samples_path}")
        return 0

    samples = [Sample.from_dict(d) for d in read_jsonl(samples_path)]

    if args.bcmd == "refs":
        target = cfg.voices_dir / "bakeoff"
        target.mkdir(parents=True, exist_ok=True)
        with _client("xtts") as client:
            for speaker in args.speaker:
                slug = VoiceSpec("xtts", voice=speaker).slug
                out = target / f"xtts-{slug}.wav"
                resp = client.synth(SynthRequest(id=slug, text=REF_TEXT, out_path=str(out), voice=speaker))
                print(f"{speaker}: {'OK' if resp.ok else resp.error} → {out}")
        return 0

    if args.bcmd == "run":
        voices = load_voice_specs(args.voices, cfg.repo_root)
        if args.engine:
            voices = [v for v in voices if v.engine in args.engine]
        new = run_bakeoff(samples, voices, _client, bake_out)
        results = _merge_results(results_path, new)
        failed = [r for r in new if not r.ok]
        for r in failed:
            print(f"FEHLER {r.engine}/{r.voice_slug}/{r.sample_id}: {r.error}", file=sys.stderr)
    else:  # sheet
        results = [BakeoffResult.from_dict(d) for d in read_jsonl(results_path)] if results_path.exists() else []

    page = write_sheet(samples, results, bake_out)
    print(f"Hörseite: {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
