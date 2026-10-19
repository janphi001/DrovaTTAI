from __future__ import annotations

import html
import random
import re
import struct
import time
import wave
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager as ContextManager
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from drova_voice.emotions import EmotionTag, Event, from_stage_directions
from drova_voice.engines.client import EngineError
from drova_voice.engines.protocol import SynthRequest
from drova_voice.jsonl import replace_with_retry
from drova_voice.loc import read_loc_file
from drova_voice.player_name import NAME_TOKEN, make_name_variants
from drova_voice.render import render_request
from drova_voice.speech_text import GVAR_RE, STAGE_RE, SpeechText, build_speech_text

BUCKETS = (
    "short",
    "long",
    "stage",
    "emotion",
    "player_name",
    "gvar",
    "question",
    "exclaim",
    "normal",
)
BAKEOFF_GVAR_FALLBACK = "zehn"

# Feste synthetische Tags für den Bucket "emotion" (neutrale Zeilen, die Emotion bekommen), reihum vergeben.
_EMOTION_PRESETS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    ("angry", 0.8, ()),
    ("sad", 0.7, ()),
    ("joyful", 0.6, ("laugh",)),
    ("stern", 0.5, ("sigh",)),
)


def _emotion_preset(n: int) -> EmotionTag:
    name, intensity, events = _EMOTION_PRESETS[n % len(_EMOTION_PRESETS)]
    return EmotionTag(name, intensity, [Event(tag, 0) for tag in events], source="manual")


@dataclass(frozen=True)
class Sample:
    sample_id: str
    source: str
    key: str
    raw: str
    text: str
    emotion: dict
    bucket: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Sample:
        return cls(**d)


def classify(raw: str) -> str:
    if NAME_TOKEN in raw:
        return "player_name"
    if "$GVAR:" in raw:
        return "gvar"
    if STAGE_RE.search(raw):
        return "stage"
    plain = raw.strip()
    if len(plain) <= 12:
        return "short"
    if len(plain) >= 200:
        return "long"
    if plain.endswith("?"):
        return "question"
    if plain.endswith("!"):
        return "exclaim"
    return "normal"


def _prepare(raw: str) -> SpeechText:
    prepared = make_name_variants(raw).arden if NAME_TOKEN in raw else raw
    values = {name: BAKEOFF_GVAR_FALLBACK for name in GVAR_RE.findall(prepared)}
    return build_speech_text(prepared, values)


def select_samples(loc_dir: Path, per_bucket: int = 4, seed: int = 42) -> list[Sample]:
    dialog = Path(loc_dir) / "Dialog"
    if not dialog.is_dir():
        raise FileNotFoundError(f"Dialog-Ordner fehlt: {dialog}")
    # Nicht sprechbare Zeilen (z. B. nur "*grinst*") gar nicht erst in den Pool,
    # sonst könnte ein Bucket je nach Zufall leer bleiben.
    pool: dict[str, list[tuple[str, str, str, SpeechText]]] = {b: [] for b in BUCKETS}
    for f in sorted(dialog.glob("NPC_*.loc")):
        for e in read_loc_file(f).entries:
            if not e.text.strip():
                continue
            st = _prepare(e.text)
            if not st.is_speakable:
                continue
            kind = classify(e.text)
            # "stage" nur mit Wirkung: mindestens eine Emotion oder ein Laut. Reine Notizen (flüstert, hick) reichen nicht.
            if kind == "stage":
                stage_tag = from_stage_directions(st.stage)
                if stage_tag.emotion == "neutral" and not stage_tag.events:
                    continue
            pool[kind].append((f.stem, e.key, e.text, st))
    rng = random.Random(seed)
    samples: list[Sample] = []
    for bucket in BUCKETS:
        if bucket == "emotion":
            # Zuerst aus den neutralen Zeilen ziehen, damit "normal" den Rest bekommt (keine Doppelten).
            normal = pool["normal"]
            picked = rng.sample(range(len(normal)), min(per_bucket, len(normal)))
            taken = set(picked)
            pool["normal"] = [row for i, row in enumerate(normal) if i not in taken]
            for n, i in enumerate(picked):
                source, key, raw, st = normal[i]
                tag = _emotion_preset(n)
                samples.append(
                    Sample(
                        f"{bucket}_{len(samples):02d}",
                        source,
                        key,
                        raw,
                        st.text,
                        tag.to_dict(),
                        bucket,
                    )
                )
            continue
        candidates = pool[bucket]
        for source, key, raw, st in rng.sample(candidates, min(per_bucket, len(candidates))):
            tag = from_stage_directions(st.stage)
            samples.append(
                Sample(
                    f"{bucket}_{len(samples):02d}", source, key, raw, st.text, tag.to_dict(), bucket
                )
            )
    if not samples:
        raise ValueError(f"Keine Zeilen gefunden in {dialog}: Stichprobe ist leer")
    return samples


REF_TEXT = (
    "Ich bin schon lange in diesen Wäldern unterwegs. Manchmal frage ich mich, "
    "ob der Weg wirklich lohnt. Doch der Morgen ist klar, und ich bleibe."
)


@dataclass(frozen=True)
class VoiceSpec:
    engine: str
    voice: str | None = None
    reference: str | None = None
    label: str | None = None

    @property
    def slug(self) -> str:
        base = (
            self.label or self.voice or (Path(self.reference).stem if self.reference else "default")
        )
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "default"


@dataclass(frozen=True)
class BakeoffResult:
    engine: str
    voice_slug: str
    sample_id: str
    ok: bool
    wav: str | None
    duration: float | None
    seconds: float
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> BakeoffResult:
        return cls(**d)


def _label(spec: VoiceSpec) -> str:
    return spec.voice or spec.reference or "default"


def _check_unique_slugs(voices: Sequence[VoiceSpec]) -> None:
    seen: dict[tuple[str, str], str] = {}
    for v in voices:
        key = (v.engine, v.slug)
        if key in seen:
            raise ValueError(
                f"Engine '{v.engine}': Stimmen '{seen[key]}' und '{_label(v)}' "
                f"ergeben beide den Ordnernamen '{v.slug}'"
            )
        seen[key] = _label(v)


def load_voice_specs(path: Path, repo_root: Path) -> list[VoiceSpec]:
    from drova_voice.fish_voices import load_fish_voices, resolve_fish_voice

    table = None
    specs = []
    for item in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []:
        ref = item.get("reference")
        if ref and not Path(ref).is_absolute():
            ref = str((Path(repo_root) / ref).resolve())
        voice, label = item.get("voice"), None
        if item["engine"] == "fish" and voice:
            if table is None:
                table = load_fish_voices(Path(repo_root) / "casting" / "fish_voices.yaml")
            found = resolve_fish_voice(table, str(voice))
            voice, label = found.id, found.key
        specs.append(VoiceSpec(item["engine"], voice, ref, label))
    _check_unique_slugs(specs)
    return specs


def _sidecar(wav: Path) -> Path:
    """Textdatei neben dem Wav: der gesendete Text, damit Änderungen am Text erkannt werden."""
    return wav.with_suffix(".txt")


def _is_finished(wav: Path, text: str) -> bool:
    side = _sidecar(wav)
    return wav.exists() and side.exists() and side.read_bytes() == text.encode("utf-8")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        if rate <= 0:
            raise ZeroDivisionError(rate)
        return handle.getnframes() / rate


def _wav_resumable(path: Path) -> bool:
    """True bei einer fertigen WAV: RIFF-Größe gleich den vorhandenen Bytes, Dauer > 0.

    Eine beim Schreiben abgebrochene Datei hat keinen gültigen Header oder eine
    RIFF-Größe, die über das Dateiende hinausreicht.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return False
    if struct.unpack_from("<I", data, 4)[0] != len(data) - 8:
        return False
    try:
        return _wav_duration(path) > 0
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return False


def _adopt_orphan_audio(wav: Path, sample_id: str, text: str) -> bool:
    """Übernimmt fertiges Audio ohne passende Sidecar-Datei, ohne neu anzufragen.

    Absturz nach dem Part-Write und vor `_sidecar`: die Part-Datei liegt noch
    unter dem Sample-Namen, oder sie wurde schon auf die Wav umbenannt. Beides
    wird behalten, wenn die Bytes eine fertige WAV sind. Ein Sidecar mit anderem
    Text bleibt ein Grund, neu zu erzeugen.
    """
    side = _sidecar(wav)
    encoded = text.encode("utf-8")
    if side.exists() and side.read_bytes() != encoded:
        return False
    part = wav.with_name(f"{sample_id}.part.wav")
    if _wav_resumable(part):
        wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            replace_with_retry(part, wav)
        except OSError as exc:
            raise OSError(
                f"Fertige Part-Datei konnte nicht übernommen werden: {part} ({exc})"
            ) from exc
        if not side.exists():
            side.write_bytes(encoded)
        return True
    if not side.exists() and _wav_resumable(wav):
        side.write_bytes(encoded)
        return True
    return False


def _synth_one(
    client, engine: str, v: VoiceSpec, s: Sample, wav: Path, text: str, params: dict
) -> BakeoffResult:
    part = wav.with_name(f"{s.sample_id}.part.wav")
    wav.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    resp = client.synth(
        SynthRequest(
            id=f"{engine}/{v.slug}/{s.sample_id}",
            text=text,
            out_path=str(part),
            voice=v.voice,
            reference=v.reference,
            params=params,
        )
    )
    seconds = time.perf_counter() - started
    if resp.ok:
        replace_with_retry(part, wav)
        _sidecar(wav).write_bytes(text.encode("utf-8"))
        return BakeoffResult(
            engine, v.slug, s.sample_id, True, str(wav), resp.duration, seconds, None
        )
    part.unlink(missing_ok=True)
    return BakeoffResult(engine, v.slug, s.sample_id, False, None, None, seconds, resp.error)


def run_bakeoff(
    samples: Sequence[Sample],
    voices: Sequence[VoiceSpec],
    client_factory: Callable[[str], ContextManager],
    out_dir: Path,
    on_result: Callable[[BakeoffResult], None] | None = None,
) -> list[BakeoffResult]:
    _check_unique_slugs(voices)
    results: list[BakeoffResult] = []

    def emit(r: BakeoffResult) -> None:
        results.append(r)
        if on_result is not None:
            on_result(r)

    for engine in dict.fromkeys(v.engine for v in voices):
        engine_voices = [v for v in voices if v.engine == engine]
        jobs = []
        for v in engine_voices:
            for s in samples:
                wav = Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav"
                text, params = render_request(engine, s.text, EmotionTag.from_dict(s.emotion))
                if _is_finished(wav, text):
                    emit(
                        BakeoffResult(engine, v.slug, s.sample_id, True, str(wav), None, 0.0, None)
                    )
                    continue
                try:
                    adopted = _adopt_orphan_audio(wav, s.sample_id, text)
                except OSError as exc:
                    emit(
                        BakeoffResult(engine, v.slug, s.sample_id, False, None, None, 0.0, str(exc))
                    )
                    continue
                if adopted:
                    emit(
                        BakeoffResult(engine, v.slug, s.sample_id, True, str(wav), None, 0.0, None)
                    )
                else:
                    jobs.append((v, s, wav, text, params))
        if not jobs:
            continue
        current = None
        t0 = time.perf_counter()
        try:
            with client_factory(engine) as client:
                for job in jobs:
                    current = job
                    t0 = time.perf_counter()
                    emit(_synth_one(client, engine, *job))
        except EngineError as e:
            # Engine gilt als ausgefallen: aktuelles Element (oder das erste) melden, Rest dieser Engine überspringen.
            v, s = (current or jobs[0])[:2]
            emit(
                BakeoffResult(
                    engine, v.slug, s.sample_id, False, None, None, time.perf_counter() - t0, str(e)
                )
            )
    return results


def _matches_line(engine: str, s: Sample, wav: Path) -> bool:
    """Gehoert die Datei zum aktuellen Text der Zeile? (Sidecar-Vergleich wie beim Wiederaufnehmen.)"""
    try:
        text, _ = render_request(engine, s.text, EmotionTag.from_dict(s.emotion))
    except ValueError:
        return False
    return _is_finished(wav, text)


def write_sheet(samples: Sequence[Sample], results: Sequence[BakeoffResult], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    by_id = {s.sample_id: s for s in samples}
    current_ids = set(by_id)
    results = [
        r for r in results if r.sample_id in current_ids
    ]  # Ergebnisse frueherer Stichproben ausblenden
    by_key = {(r.engine, r.voice_slug, r.sample_id): r for r in results}
    columns = sorted({(r.engine, r.voice_slug) for r in results})
    esc = html.escape
    head = "".join(f"<th>{esc(e)}<br><small>{esc(v)}</small></th>" for e, v in columns)
    rows = []
    for s in samples:
        cells = []
        for e, v in columns:
            r = by_key.get((e, v, s.sample_id))
            if r and r.ok and r.wav and not _matches_line(e, s, Path(r.wav)):
                cells.append(
                    "<td>– veraltet (Text der Zeile hat sich geändert, bitte neu erzeugen)</td>"
                )
            elif r and r.ok and r.wav:
                wav_path = Path(r.wav).resolve()
                try:
                    src = wav_path.relative_to(out_dir.resolve()).as_posix()
                except ValueError:  # liegt außerhalb der Hörseite: absolute file://-URI
                    src = wav_path.as_uri()
                cells.append(f'<td><audio controls preload="none" src="{esc(src)}"></audio></td>')
            else:
                cells.append(f"<td>– {esc(r.error) if r and r.error else ''}</td>")
        emo = s.emotion.get("emotion", "neutral")
        events = ", ".join(ev["tag"] for ev in s.emotion.get("events", []))
        rows.append(
            f"<tr><td><b>{esc(s.bucket)}</b><br>{esc(s.text)}<br><small>{esc(emo)} {esc(events)} · {esc(s.source)}/{esc(s.key)}</small></td>{''.join(cells)}</tr>"
        )
    summary = []
    for e, v in columns:
        timed = [
            r
            for r in results
            if (r.engine, r.voice_slug) == (e, v)
            and r.ok
            and r.duration
            and r.wav is not None
            and _matches_line(e, by_id[r.sample_id], Path(r.wav))
        ]
        dur = sum(r.duration or 0.0 for r in timed)
        sec = sum(r.seconds for r in timed)
        rtf = f"{sec / dur:.2f}" if dur else "–"
        summary.append(
            f"<tr><td>{esc(e)} / {esc(v)}</td><td>{dur:.1f} s</td><td>{sec:.1f} s</td><td>{rtf}</td></tr>"
        )
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>DrovaVoice Hörtest</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}audio{{width:220px}}</style>
</head><body><h1>DrovaVoice Hörtest</h1>
<h2>Geschwindigkeit</h2><table><tr><th>Engine / Stimme</th><th>Audio</th><th>Rechenzeit</th><th>Echtzeitfaktor</th></tr>{"".join(summary)}</table>
<h2>Zeilen</h2><table><tr><th>Zeile</th>{head}</tr>{"".join(rows)}</table></body></html>"""
    path = out_dir / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
