from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from drova_voice.assign import assign
from drova_voice.casting import (
    cast_report,
    load_casting,
    tree_conflicts,
    voice_speakers,
    write_auto_casting,
)
from drova_voice.casting_sheet import write_casting_sheet
from drova_voice.config import Config
from drova_voice.emote import (
    import_llm_emotions,
    merge_emotions,
    prepare_emote_packets,
    read_emotions,
    write_emotions,
)
from drova_voice.encode import run_encode
from drova_voice.engines.client import EngineClient, EngineError, cache_env, worker_command
from drova_voice.export_report import locate_manifest
from drova_voice.fish_model import (
    free_tier_warning,
    guard_fish_model,
    resolve_fish_profile,
    write_model_stamp,
)
from drova_voice.fish_voices import load_catalog
from drova_voice.ids import VARIANT_SEP, with_variant
from drova_voice.install import install_audio
from drova_voice.jsonl import (
    append_jsonl,
    latest_by_id,
    read_jsonl_counted,
    read_jsonl_lenient,
    write_jsonl,
)
from drova_voice.lines import (
    Line,
    build_lines,
    emotion_id,
    load_lexicon,
    load_loc_texts,
    read_lines,
    select_npc,
    write_lines,
)
from drova_voice.pools import (
    expand_pool_lines,
    expand_teacher_lines,
    load_pools,
    load_teachers,
)
from drova_voice.preview import write_preview
from drova_voice.profiles import (
    LOW_CONFIDENCE,
    Profile,
    merge_import,
    prepare_packets,
    read_profiles,
    write_profiles,
)
from drova_voice.report import (
    build_report,
    build_speaker_report,
    format_report,
    format_speaker_report,
)
from drova_voice.selection import (
    DEFAULT_BATCH_CHARS,
    batch_lines,
    plan_batches,
    read_batches,
    sample_lines,
    speaker_stats,
    write_batches,
)
from drova_voice.synth import SynthJob, SynthStatus, build_jobs, run_synth
from drova_voice.voice_check import SKIPPED, api_key, query_voices, summarize, used_voices

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"


def _fail(message: str) -> int:
    print(f"FEHLER: {message}", file=sys.stderr)
    return 2


def read_json_object(path: Path, what: str) -> dict | None:
    """JSON-Objekt lesen. None (mit Meldung), wenn die Datei unlesbar oder kein Objekt ist."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        _fail(f"{what} nicht lesbar: {path} ({e})")
        return None
    if not isinstance(data, dict):
        _fail(f"{what} ist kein JSON-Objekt: {path}")
        return None
    return data


def lines_path(cfg: Config) -> Path:
    return cfg.data_dir / "lines.jsonl"


def batches_path(cfg: Config) -> Path:
    return cfg.data_dir / "batches.json"


def _selected(cfg: Config, args: argparse.Namespace, expand_pool: bool = True) -> list[Line] | None:
    """Zeilen aus data/lines.jsonl, gefiltert nach --npc (ganze Bäume), --sample (eine Zeile je Sprecher) und
    --batch N (Etappe) und --category; Zeilen generischer Sprecher werden je Poolstimme erweitert (casting/pools.yaml),
    Lehrerzeilen zusätzlich je Lehrer (casting/teachers.yaml),
    außer bei `emote` (Emotionen gelten für die Basiszeile). None (mit Meldung), wenn die Auswahl nicht möglich ist."""
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
    if getattr(args, "sample", False):
        lines = sample_lines(lines)
    batch_n = getattr(args, "batch", None)
    if batch_n is not None:
        if not batches_path(cfg).is_file():
            _fail(f"{batches_path(cfg)} fehlt (zuerst `drova-voice batches` ausführen)")
            return None
        chosen = [b for b in read_batches(batches_path(cfg)) if b.n == batch_n]
        if not chosen:
            _fail(f"Etappe {batch_n} gibt es nicht (siehe `drova-voice batches`)")
            return None
        lines = batch_lines(lines, chosen[0])
    category = getattr(args, "category", None)
    if category:
        lines = [l for l in lines if l.category == category]
    if expand_pool:
        try:
            pools = load_pools(
                cfg.casting_dir / "pools.yaml",
                load_catalog(cfg.casting_dir / "fish_voices.yaml").known(),
            )
            teachers = load_teachers(cfg.casting_dir / "teachers.yaml")
        except (OSError, ValueError) as e:
            _fail(str(e))
            return None
        lines = expand_teacher_lines(expand_pool_lines(lines, pools), lines, teachers)
    return lines


def _extract(cfg: Config, args: argparse.Namespace) -> int:
    manifest_path, notice = locate_manifest(cfg.data_dir / "export" / cfg.language, args.manifest)
    if manifest_path is None:
        return _fail(notice or "Manifest nicht gefunden")
    if not cfg.loc_dir.is_dir():
        return _fail(
            f"Lokalisierungsordner nicht gefunden: {cfg.loc_dir} (game_dir in config.yaml prüfen)"
        )
    if notice:
        print(notice)
    manifest = read_json_object(manifest_path, "Manifest")
    if manifest is None:
        return 2
    if not isinstance(manifest.get("lines", []), list):
        return _fail(f"Manifest: lines ist keine Liste ({manifest_path})")
    lexicon = load_lexicon(cfg.casting_dir / "lexicon.yaml")
    lines = build_lines(manifest, load_loc_texts(cfg.loc_dir, cfg.language), lexicon)
    write_lines(lines_path(cfg), lines)
    skips = Counter(l.skip for l in lines if l.skip)
    detail = ", ".join(f"{reason}: {n}" for reason, n in sorted(skips.items())) or "keine"
    print(f"{len(lines)} Zeilen -> {lines_path(cfg)}; übersprungen: {detail}")
    return 0


def auto_casting_path(cfg: Config) -> Path:
    return cfg.casting_dir / "casting_auto.yaml"


def _load_casting(cfg: Config):
    catalog = load_catalog(cfg.casting_dir / "fish_voices.yaml")
    return catalog, load_casting(
        cfg.casting_dir / "casting.yaml",
        catalog.known(),
        auto_casting_path(cfg),
        cfg.casting_dir / "pools.yaml",
    )


def _cast(cfg: Config, args: argparse.Namespace) -> int:
    if args.check_voices:
        return _cast_check_voices(cfg)
    if args.propose:
        return _cast_propose(cfg, args)
    if args.listen:
        return _cast_listen(cfg)
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        _, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    report = cast_report(lines, casting)
    print(
        "Stimmen (Zeilen): "
        + (", ".join(f"{v}: {n}" for v, n in sorted(report.usage.items())) or "keine")
    )
    print(
        "Sprecher ohne Stimme: "
        + (", ".join(f"{a}: {n}" for a, n in sorted(report.missing.items())) or "keine")
    )
    crowded = {
        v: sorted(who)
        for v, who in voice_speakers(lines, casting).items()
        if len(who) > args.max_speakers
    }
    if crowded:
        print(
            f"Überbelegt (mehr als {args.max_speakers} Sprecher): "
            + "; ".join(f"{v}: {len(who)}" for v, who in sorted(crowded.items()))
        )
    conflicts = tree_conflicts(lines, casting)
    if conflicts:
        print(f"Gleiche Stimme im selben Baum: {len(conflicts)} Fälle")
        for tree, voice, who in conflicts[:10]:
            print(f"  {tree}: {voice} ({', '.join(who)})")
    return 1 if report.missing else 0


def _cast_propose(cfg: Config, args: argparse.Namespace) -> int:
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    try:
        catalog = load_catalog(cfg.casting_dir / "fish_voices.yaml")
        manual = load_casting(cfg.casting_dir / "casting.yaml", catalog.known())
        keep = auto_casting_path(cfg).is_file() and not args.reset
        # nur beim Behalten wird die alte Auto-Datei geladen (und geprüft); --reset verwirft sie ungesehen
        merged = (
            load_casting(cfg.casting_dir / "casting.yaml", catalog.known(), auto_casting_path(cfg))
            if keep
            else None
        )
        profiles = read_profiles(profiles_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    stats = speaker_stats(lines)
    kept = (
        {n: v for n, v in merged.speakers.items() if n not in manual.speakers}
        if merged is not None
        else {}
    )
    result = assign(stats, profiles, catalog.candidates(), {**kept, **manual.speakers})
    write_auto_casting(auto_casting_path(cfg), {**kept, **result.voices})
    if keep:
        print("Bisherige Auto-Zuteilung bleibt (--reset verwirft sie)")
    else:
        print("Neu zugeteilt (--reset)" if args.reset else "Neu zugeteilt (erste Zuteilung)")
    print(
        f"{len(result.voices)} Sprecher neu zugeteilt, {len(kept)} behalten, {len(manual.speakers)} von Hand besetzt "
        f"-> {auto_casting_path(cfg)}"
    )
    display = {s.name: s.display for s in stats}
    if result.open:
        print("Offen (kein Steckbrief): " + ", ".join(display[n] for n in result.open))
    for name, why in sorted(result.emergency.items()):
        print(f"Notbesetzung {display[name]}: {why}")
    speakers_by_voice = Counter({**Counter(kept.values()), **Counter(manual.speakers.values())})
    speakers_by_voice.update(result.voices.values())
    print(
        "Stimmen (Sprecher): "
        + ", ".join(f"{v}: {n}" for v, n in sorted(speakers_by_voice.items()))
    )
    return 1 if result.open else 0


def _cast_check_voices(cfg: Config) -> int:
    """Fish-IDs der Besetzung prüfen. Ohne Schlüssel kein Aufruf und Exit 0."""
    if not api_key():
        print(SKIPPED)
        return 0
    try:
        catalog, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    rows = used_voices(catalog, casting)
    if not rows:
        print("Stimmenprüfung: keine genutzten Stimmen.")
        return 0
    table = catalog.synth_table()
    ids = {row.voice_id for row in rows}
    for target in catalog.fallbacks.values():
        if target in table:
            ids.add(table[target].id)
    try:
        found = query_voices(WORKERS_DIR, sorted(ids))
    except EngineError as e:
        return _fail(str(e))
    lines, code = summarize(
        rows,
        {
            item["id"]: item
            for item in found
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        },
        catalog,
    )
    print("\n".join(lines))
    return code


def _cast_listen(cfg: Config) -> int:
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    try:
        catalog, casting = _load_casting(cfg)
        profiles = read_profiles(profiles_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    samples = {l.actor.lower(): l for l in sample_lines(lines)}
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    page = write_casting_sheet(
        speaker_stats(lines),
        casting,
        catalog.candidates(),
        profiles,
        samples,
        encoded,
        audio_dir(cfg),
        cfg.out_dir / "casting" / "index.html",
    )
    heard = sum(1 for l in samples.values() if l.id in encoded)
    print(f"Hörseite: {page} ({heard} von {len(samples)} Beispielen mit Ton)")
    return 0


def _read_import_rows(files: list[Path]) -> tuple[list[dict], list[str]] | None:
    """Zeilen der Importdateien plus Fehlermeldungen zu unlesbaren Zeilen; None (mit Meldung), wenn eine Datei fehlt."""
    for f in files:
        if not Path(f).is_file():
            _fail(f"Importdatei nicht gefunden: {f}")
            return None
    rows: list[dict] = []
    errors: list[str] = []
    for f in files:
        file_rows, skipped = read_jsonl_counted(f)
        rows.extend(file_rows)
        if skipped:
            errors.append(f"{skipped} unlesbare Zeilen in {f} übersprungen")
    return rows, errors


def _print_import_errors(errors: list[str], limit: int = 20) -> None:
    for e in errors[:limit]:
        print(f"FEHLER {e}", file=sys.stderr)
    if len(errors) > limit:
        print(f"... und {len(errors) - limit} weitere Fehler", file=sys.stderr)


def emotions_path(cfg: Config) -> Path:
    return cfg.casting_dir / "emotions.jsonl"


def _emote(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args, expand_pool=False)
    if lines is None:
        return 2
    try:
        existing = read_emotions(emotions_path(cfg))
        profiles = read_profiles(profiles_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    if args.prepare:
        if args.size < 1:
            return _fail("--size muss mindestens 1 sein")
        packets = prepare_emote_packets(lines, profiles, args.size)
        out = cfg.out_dir / "subagent" / "emote"
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("packet_*.json"):
            old.unlink()
        for i, packet in enumerate(packets, start=1):
            (out / f"packet_{i:03d}.json").write_text(
                json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        print(f"{sum(len(p) for p in packets)} Dialogbäume in {len(packets)} Paketen -> {out}")
        return 0
    if args.import_files:
        loaded = _read_import_rows(args.import_files)
        if loaded is None:
            return 2
        rows, read_errors = loaded
        result = import_llm_emotions(existing, rows, {l.id for l in lines if not l.skip})
        write_emotions(emotions_path(cfg), result.merged)
        print(
            f"{result.imported} LLM-Emotionen übernommen, {result.kept} feste Zeilen behalten -> {emotions_path(cfg)}"
        )
        errors = read_errors + result.errors
        _print_import_errors(errors)
        return 1 if errors else 0
    merged = merge_emotions(existing, lines)
    write_emotions(emotions_path(cfg), merged)
    sources = Counter(t.source for t in merged.values())
    print(
        f"{len(merged)} Emotionen -> {emotions_path(cfg)}; "
        + ", ".join(f"{s}: {n}" for s, n in sorted(sources.items()))
    )
    return 0


def synth_results_path(cfg: Config) -> Path:
    return cfg.data_dir / "synth" / "results.jsonl"


def _same_synth_result(previous: dict, row: dict) -> bool:
    return all(previous.get(field) == row.get(field) for field in ("key", "wav", "ok"))


def record_synth_results(path: Path, fresh: list[dict]) -> None:
    """Eine Zeile je id. Unveränderte Cache-Treffer (gleicher key, wav, ok) ersetzen den Stand nicht.
    Schreiben passiert einmal am Ende, atomar, damit die Datei nicht bei jedem Lauf um alle Aufträge wächst."""
    if not fresh:
        return
    existing = read_jsonl_lenient(path)
    merged = latest_by_id(existing)
    changed = False
    for row in fresh:
        row_id = row.get("id")
        if not isinstance(row_id, str):
            continue
        previous = merged.get(row_id)
        if previous is not None and _same_synth_result(previous, row):
            continue
        merged[row_id] = row
        changed = True
    if changed or len(existing) != len(merged):
        write_jsonl(path, merged.values())


def usage_path(cfg: Config) -> Path:
    return cfg.data_dir / "synth" / "usage.jsonl"


def _client_factory(cfg: Config, fish_env: dict[str, str] | None):
    def make(engine: str) -> EngineClient:
        env = dict(cache_env(cfg.cache_dir))
        if engine == "fish" and fish_env:
            env.update(fish_env)  # dieselbe ID, Sprache und Sampling wie im Cache-Schlüssel
        return EngineClient(worker_command(WORKERS_DIR, engine), env=env)

    return make


def _synth(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        catalog, casting = _load_casting(cfg)
        emotions = read_emotions(emotions_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    jobs, skipped = build_jobs(lines, casting, catalog.synth_table(), emotions, args.engine)
    if args.limit is not None:
        if args.limit < 0:
            return _fail("--limit muss 0 oder größer sein")
        jobs = jobs[: args.limit]
    cache_dir = cfg.cache_dir / "synth"
    model_alias = None
    fish_env = None
    if args.engine == "fish":
        try:
            profile = resolve_fish_profile(
                cfg.language, cfg.fish_model, cfg.fish_latency, cfg.fish_temperature, cfg.fish_top_p
            )
        except ValueError as e:
            return _fail(str(e))
        jobs = [
            SynthJob(j.id, j.text, j.speech_len, j.voice, {**j.params, **profile.params()})
            for j in jobs
        ]
        model_alias = profile.cache_model()
        proceed, notice = guard_fish_model(cache_dir, profile.stamp(), args.accept_model_change)
        if notice:
            print(notice, file=sys.stderr)
        if not proceed:
            return 2
        write_model_stamp(cache_dir, profile.stamp())
        expired = free_tier_warning(profile.model_id)
        if expired:
            print(expired, file=sys.stderr)
        print(f"Cache-Schlüssel: {profile.stamp()}")
        fish_env = profile.worker_env()
    path = synth_results_path(cfg)
    status = SynthStatus()
    budget = getattr(args, "max_utf8_bytes", None)
    if budget is not None and budget < 1:
        return _fail("--max-utf8-bytes muss mindestens 1 sein")
    recorded: list[dict] = []
    # Auch bei Abbruch (Strg+C, zu viele Fehler) landet, was bis dahin fertig war, in results.jsonl.
    try:
        results = run_synth(
            jobs,
            args.engine,
            _client_factory(cfg, fish_env),
            cache_dir,
            args.workers,
            on_result=lambda r: recorded.append(r.to_dict()),
            status=status,
            max_utf8_bytes=budget,
            model=model_alias,
        )
    finally:
        record_synth_results(path, recorded)
    done = [r for r in results if r.ok]
    new = [r for r in done if r.attempts > 0]
    failed = [r for r in results if not r.ok]
    flagged = [r for r in done if r.flagged]
    reasons = Counter(skipped.values())
    detail = ", ".join(f"{k}: {n}" for k, n in sorted(reasons.items())) or "keine"
    print(
        f"{len(done)} erzeugt ({len(done) - len(new)} aus dem Cache, {len(new)} neu erzeugt), {len(failed)} Fehler, "
        f"{len(flagged)} auffällige Dauer; übersprungen: {detail}"
    )
    unique_new = {r.key: r for r in new}  # Zeilen mit neuem Ton; Zeichen und Bytes stehen in status
    # HTTP-POSTs inklusive Worker-Wiederholungen. Ohne Worker-Zählung ist es die Zahl der Aufrufe.
    requests = sum({r.key: r.attempts for r in results if r.attempts > 0}.values())
    append_jsonl(
        usage_path(cfg),
        {
            "at": datetime.now().isoformat(timespec="seconds"),
            "engine": args.engine,
            "lines": len(unique_new),
            "requests": requests,
            "chars": status.sent_chars,
            "utf8_bytes": status.sent_bytes,
        },
    )
    history = [
        row for row in read_jsonl_lenient(usage_path(cfg)) if row.get("engine") == args.engine
    ]
    total_chars = sum(row.get("chars", 0) for row in history)
    # Ältere Zeilen haben nur `chars`. Die sind eine Untergrenze der UTF-8-Bytes.
    total_bytes = sum(
        row["utf8_bytes"] if "utf8_bytes" in row else row.get("chars", 0) for row in history
    )
    print(
        f"Zeichen neu an {args.engine} gesendet: {status.sent_chars} "
        f"({status.sent_bytes} UTF-8-Bytes, {requests} Anfragen); "
        f"insgesamt bisher: {total_chars} ({total_bytes} UTF-8-Bytes)"
    )
    for r in failed[:10]:
        print(f"FEHLER {r.id}: {r.error}", file=sys.stderr)
    for r in flagged[:10]:
        print(f"AUFFÄLLIG {r.id}: Dauer {r.duration:.1f} s", file=sys.stderr)
    if status.aborted:
        print(
            f"ABBRUCH: {status.aborted}; {status.not_run} Aufträge nicht gestartet (später `synth` erneut ausführen, "
            f"Fertiges kommt aus dem Cache)",
            file=sys.stderr,
        )
    return 1 if failed or status.aborted else 0


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
        return _fail(
            f"{synth_results_path(cfg)} fehlt oder ist leer (zuerst `drova-voice synth` ausführen)"
        )
    try:
        catalog, casting = _load_casting(cfg)
        emotions = read_emotions(emotions_path(cfg))
        variants = {
            l.id: catalog.variants[casting.voice_for(l)]
            for l in lines
            if not l.skip and casting.voice_for(l) in catalog.variants
        }
        rows, errors = run_encode(
            lines, synth_rows, emotions, audio_dir(cfg), args.workers, variants
        )
    except (OSError, ValueError) as e:
        return _fail(str(e))
    merged = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    merged.update({r["id"]: r for r in rows})
    write_jsonl(encoded_path(cfg), merged.values())
    print(f"{len(rows)} kodiert -> {audio_dir(cfg)}; {len(errors)} Fehler")
    for err in errors[:10]:
        print(f"FEHLER {err}", file=sys.stderr)
    return 1 if errors else 0


def _install(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    if not encoded:
        return _fail(
            f"{encoded_path(cfg)} fehlt oder ist leer (zuerst `drova-voice encode` ausführen)"
        )
    try:
        _, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    synth_rows = latest_by_id(read_jsonl_lenient(synth_results_path(cfg)))
    active = {l.id for l in lines if not l.skip and casting.voice_for(l) is not None}
    rows, stale = [], []
    for line_id, row in encoded.items():
        if line_id not in active:
            continue
        synth_row = synth_rows.get(line_id)
        if synth_row is None or not synth_row.get("ok") or synth_row.get("key") != row.get("key"):
            stale.append(f"{line_id}: Ton ist veraltet (synth und encode erneut ausführen)")
        else:
            rows.append(row)
    drop = {l.id for l in lines} - {r["id"] for r in rows}
    # Ein installierter Basis-Eintrag verdrängt eine alte neutrale Variante (die Mod bevorzugt Varianten).
    drop |= {
        with_variant(l.id, "neutral") for l in lines if not l.skip and VARIANT_SEP not in l.id
    } - {r["id"] for r in rows}
    # Poolzeilen: alle Varianten der Basis-ID neu aufbauen, damit Stimmen, die aus dem Pool gefallen sind, verschwinden.
    drop |= {emotion_id(l) for l in lines if l.pool}
    prune = bool(getattr(args, "prune", False))
    dry_run = bool(getattr(args, "dry_run", False))
    result = install_audio(
        rows,
        audio_dir(cfg),
        cfg.install_dir,
        cfg.language,
        drop_ids=drop,
        prune=prune,
        dry_run=dry_run,
        audio_root=cfg.game_dir / "Mods" / "DrovaVoice" / "Audio",
        game_dir=cfg.game_dir,
    )
    result.errors.extend(stale)
    if dry_run:
        print(
            f"würde {result.copied} kopieren, {result.entries} Einträge, {len(result.pruned)} verwaist"
        )
    else:
        print(
            f"{result.copied} Dateien kopiert, index.json mit {result.entries} Einträgen -> {cfg.install_dir}"
        )
        if prune:
            print(f"gelöscht: {len(result.pruned)} verwaiste OGG")
    if dry_run or prune:
        for rel in result.pruned:
            print(f"  {rel}")
    for err in result.errors[:10]:
        print(f"FEHLER {err}", file=sys.stderr)
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
    entries: dict = {}
    if index_path.is_file():
        index = read_json_object(index_path, "index.json")
        if index is None:
            return 2
        entries = index.get("entries", {})
        if not isinstance(entries, dict):
            return _fail(f"index.json: entries ist kein Objekt ({index_path})")
    synth_rows = latest_by_id(read_jsonl_lenient(synth_results_path(cfg)))
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    if args.by_speaker:
        print(
            format_speaker_report(
                build_speaker_report(lines, casting, synth_rows, encoded, entries), casting
            )
        )
        return 0
    print(format_report(build_report(lines, casting, synth_rows, encoded, entries)))
    return 0


def _preview(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        emotions = read_emotions(emotions_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    page = write_preview(
        lines,
        latest_by_id(read_jsonl_lenient(encoded_path(cfg))),
        emotions,
        audio_dir(cfg),
        cfg.out_dir / "preview" / "index.html",
        f"Hörprobe {args.npc or 'alle Zeilen'}",
    )
    print(f"Hörseite: {page}")
    return 0


def _batches(cfg: Config, args: argparse.Namespace) -> int:
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    batches = plan_batches(lines, args.max_chars)
    write_batches(batches_path(cfg), batches, args.max_chars)
    display = {s.name: s.display for s in speaker_stats(lines)}
    for b in batches:
        who = ", ".join(display[n] for n in b.speakers[:6]) + (
            ", ..." if len(b.speakers) > 6 else ""
        )
        print(
            f"Etappe {b.n}: {len(b.speakers)} Sprecher{' + Spieler' if b.player else ''}, {b.lines} Zeilen, {b.chars} Zeichen ({who})"
        )
    print(f"{len(batches)} Etappen, {sum(b.chars for b in batches)} Zeichen -> {batches_path(cfg)}")
    return 0


def profiles_path(cfg: Config) -> Path:
    return cfg.casting_dir / "profiles.jsonl"


def _profile(cfg: Config, args: argparse.Namespace) -> int:
    try:
        profiles = read_profiles(profiles_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    if args.set:
        if not args.gender or not args.age:
            return _fail("--set braucht --gender und --age")
        try:
            p = Profile.from_dict(
                {
                    "speaker": args.set,
                    "gender": args.gender,
                    "age": args.age,
                    "type": args.type,
                    "confidence": 1.0,
                    "note": args.note or "",
                    "source": "manual",
                }
            )
        except ValueError as e:
            return _fail(str(e))
        profiles[p.speaker] = p
        write_profiles(profiles_path(cfg), profiles.values())
        print(
            f"{p.speaker}: {p.gender}, {p.age}{', ' + p.type if p.type else ''} -> {profiles_path(cfg)}"
        )
        return 0
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    if args.prepare:
        if args.size < 1:
            return _fail("--size muss mindestens 1 sein")
        packets = prepare_packets(lines, profiles, args.size, include_known=args.all)
        out = cfg.out_dir / "subagent" / "profile"
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("packet_*.json"):
            old.unlink()
        for i, packet in enumerate(packets, start=1):
            (out / f"packet_{i:03d}.json").write_text(
                json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        print(f"{sum(len(p) for p in packets)} Sprecher in {len(packets)} Paketen -> {out}")
        return 0
    if args.import_files:
        loaded = _read_import_rows(args.import_files)
        if loaded is None:
            return 2
        rows, read_errors = loaded
        merged, merge_errors = merge_import(profiles, rows, {s.name for s in speaker_stats(lines)})
        write_profiles(profiles_path(cfg), merged.values())
        print(
            f"{len(merged)} Steckbriefe ({len(merged) - len(profiles)} neu) -> {profiles_path(cfg)}"
        )
        errors = read_errors + merge_errors
        _print_import_errors(errors)
        return 1 if errors else 0
    stats = speaker_stats(lines)
    for s in stats:
        found = profiles.get(s.name)
        if found is None:
            print(f"{s.display} ({s.lines}): kein Steckbrief")
        else:
            flag = " UNSICHER" if found.confidence < LOW_CONFIDENCE else ""
            print(
                f"{s.display} ({s.lines}): {found.gender}, {found.age}{', ' + found.type if found.type else ''}, "
                f"{found.confidence:.1f}{flag}, {found.source}: {found.note}"
            )
    print(
        f"{sum(1 for s in stats if s.name in profiles)} von {len(stats)} Sprechern haben einen Steckbrief"
    )
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
    "batches": _batches,
    "profile": _profile,
}


def _add_selection(parser, npc_help: str = "nur Bäume, in denen dieser NPC spricht") -> None:
    parser.add_argument("--npc", help=npc_help)
    parser.add_argument(
        "--sample", action="store_true", help="nur eine Beispielzeile je Sprecher (Hörstufe)"
    )
    parser.add_argument("--batch", type=int, help="nur die Zeilen dieser Etappe (siehe `batches`)")
    parser.add_argument(
        "--category", choices=("dialog", "bark", "player"), help="nur Zeilen dieser Kategorie"
    )


def add_parsers(sub) -> None:
    ex = sub.add_parser("extract", help="Manifest + .loc -> data/lines.jsonl (Sprechtext)")
    ex.add_argument("--manifest", type=Path, help="Standard: data/export/<Sprache>/manifest.json")
    cast = sub.add_parser(
        "cast", help="Besetzung prüfen (--check) oder aus Steckbriefen vorschlagen (--propose)"
    )
    cast.add_argument(
        "--check",
        action="store_true",
        help="nur prüfen (Standard und einzige Betriebsart in Plan 3)",
    )
    cast.add_argument(
        "--check-voices",
        action="store_true",
        help="genutzte Fish-IDs gegen die API prüfen (ohne FISH_API_KEY übersprungen)",
    )
    cast.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
    cast.add_argument(
        "--propose",
        action="store_true",
        help="Stimmen aus den Steckbriefen zuteilen (casting/casting_auto.yaml)",
    )
    cast.add_argument(
        "--listen",
        action="store_true",
        help="Hörseite out/casting/index.html (nach synth/encode --sample)",
    )
    cast.add_argument(
        "--keep",
        action="store_true",
        help="mit --propose: bisherige Auto-Zuteilung behalten (jetzt Standard, nur noch Synonym)",
    )
    cast.add_argument(
        "--reset",
        action="store_true",
        help="mit --propose: bisherige Auto-Zuteilung verwerfen und alles neu zuteilen",
    )
    cast.add_argument(
        "--max-speakers",
        type=int,
        default=12,
        help="--check: ab so vielen Sprechern gilt eine Stimme als überbelegt",
    )
    em = sub.add_parser(
        "emote",
        help="Emotionen aus Regieanweisungen nach casting/emotions.jsonl (llm/manual bleiben)",
    )
    _add_selection(em)
    em.add_argument(
        "--prepare",
        action="store_true",
        help="Dialogbäume als Pakete für Subagents nach out/subagent/emote schreiben",
    )
    em.add_argument("--size", type=int, default=20, help="Dialogbäume je Paket (Standard 20)")
    em.add_argument(
        "--import",
        dest="import_files",
        nargs="+",
        type=Path,
        metavar="DATEI",
        help="JSONL-Ergebnisse der Subagents einlesen",
    )
    sy = sub.add_parser(
        "synth", help="Sprache erzeugen (Cache unter cache/synth, wiederaufnehmbar)"
    )
    sy.add_argument("--engine", default="fish")
    sy.add_argument(
        "--accept-model-change",
        action="store_true",
        help="Wechsel von Modell, Sprache, Latenz oder Sampling bestätigen (vorhandener Fish-Cache gilt dann als Fehltreffer)",
    )
    sy.add_argument(
        "--workers",
        type=int,
        default=8,
        help="parallele Anfragen (Standard 8, gemessen ohne 429 bis 16)",
    )
    sy.add_argument("--limit", type=int, help="nur die ersten N Aufträge (0 sendet nichts)")
    sy.add_argument(
        "--max-utf8-bytes",
        type=int,
        help="höchstens so viele UTF-8-Bytes neu senden, danach abbrechen (Cache zählt nicht)",
    )
    _add_selection(sy)
    en = sub.add_parser(
        "encode", help="WAV -> OGG (Stille trimmen, -16 LUFS, mono) nach out/audio/<Sprache>"
    )
    en.add_argument("--workers", type=int, default=4)
    _add_selection(en)
    ins = sub.add_parser(
        "install", help="Dateien in den Mod-Ordner kopieren und index.json schreiben"
    )
    _add_selection(
        ins, "nur Bäume, in denen dieser NPC spricht (frühere Einträge bleiben erhalten)"
    )
    ins.add_argument(
        "--prune",
        action="store_true",
        help="verwaiste OGG im Zielordner löschen (stehen danach nicht im Index; Standard: aus)",
    )
    ins.add_argument(
        "--dry-run",
        action="store_true",
        help="nichts kopieren und index.json nicht schreiben; nur zählen und auflisten "
        "(würde N kopieren, M Einträge, K verwaist; gilt auch zusammen mit --prune)",
    )
    rp = sub.add_parser(
        "report", help="Status je Kategorie: offen, erzeugt, kodiert, installiert, übersprungen"
    )
    _add_selection(rp)
    rp.add_argument(
        "--by-speaker", action="store_true", help="Status je Sprecher statt je Kategorie"
    )
    pv = sub.add_parser(
        "preview", help="Hörseite out/preview/index.html (Zeilen mit Emotion und Audio)"
    )
    _add_selection(pv)
    bt = sub.add_parser("batches", help="Etappen für den Vollauf planen (data/batches.json)")
    bt.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_BATCH_CHARS,
        help="Zeichen je Etappe (Standard 100000)",
    )
    pr = sub.add_parser(
        "profile",
        help="Steckbriefe der Sprecher (casting/profiles.jsonl): Pakete für Subagents, Import, Anzeige",
    )
    pr.add_argument(
        "--prepare",
        action="store_true",
        help="Pakete für Subagents nach out/subagent/profile schreiben",
    )
    pr.add_argument("--size", type=int, default=20, help="Sprecher je Paket (Standard 20)")
    pr.add_argument(
        "--all", action="store_true", help="auch Sprecher mit Steckbrief in die Pakete aufnehmen"
    )
    pr.add_argument(
        "--import",
        dest="import_files",
        nargs="+",
        type=Path,
        metavar="DATEI",
        help="JSONL-Ergebnisse der Subagents einlesen",
    )
    pr.add_argument(
        "--set", metavar="NAME", help="Steckbrief von Hand setzen (braucht --gender und --age)"
    )
    pr.add_argument("--gender", choices=["m", "f"])
    pr.add_argument("--age", choices=["kind", "jung", "mittel", "alt"])
    pr.add_argument("--type", choices=["riese", "zwerg", "schurke"])
    pr.add_argument("--note", help="ein Satz zum Charakter, ohne wörtliche Zitate")
