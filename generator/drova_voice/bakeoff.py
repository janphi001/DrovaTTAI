from __future__ import annotations

import html
import random
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, ContextManager, Sequence

import yaml

from drova_voice.emotions import EmotionTag, from_stage_directions
from drova_voice.engines.protocol import SynthRequest
from drova_voice.loc import read_loc_file
from drova_voice.render import render_request
from drova_voice.player_name import NAME_TOKEN, make_name_variants
from drova_voice.speech_text import GVAR_RE, STAGE_RE, SpeechText, build_speech_text

BUCKETS = ("short", "long", "stage", "player_name", "gvar", "question", "exclaim", "normal")
BAKEOFF_GVAR_FALLBACK = "zehn"


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
    def from_dict(cls, d: dict) -> "Sample":
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
    # Nicht sprechbare Zeilen (z. B. nur "*grinst*") gar nicht erst in den Pool,
    # sonst könnte ein Bucket je nach Zufall leer bleiben.
    pool: dict[str, list[tuple[str, str, str, SpeechText]]] = {b: [] for b in BUCKETS}
    for f in sorted((Path(loc_dir) / "Dialog").glob("NPC_*.loc")):
        for e in read_loc_file(f).entries:
            if not e.text.strip():
                continue
            st = _prepare(e.text)
            if st.is_speakable:
                pool[classify(e.text)].append((f.stem, e.key, e.text, st))
    rng = random.Random(seed)
    samples: list[Sample] = []
    for bucket in BUCKETS:
        candidates = pool[bucket]
        for source, key, raw, st in rng.sample(candidates, min(per_bucket, len(candidates))):
            tag = from_stage_directions(st.stage)
            samples.append(Sample(f"{bucket}_{len(samples):02d}", source, key, raw, st.text, tag.to_dict(), bucket))
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

    @property
    def slug(self) -> str:
        base = self.voice or (Path(self.reference).stem if self.reference else "default")
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
    def from_dict(cls, d: dict) -> "BakeoffResult":
        return cls(**d)


def load_voice_specs(path: Path, repo_root: Path) -> list[VoiceSpec]:
    specs = []
    for item in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []:
        ref = item.get("reference")
        if ref and not Path(ref).is_absolute():
            ref = str((Path(repo_root) / ref).resolve())
        specs.append(VoiceSpec(item["engine"], item.get("voice"), ref))
    return specs


def run_bakeoff(
    samples: Sequence[Sample],
    voices: Sequence[VoiceSpec],
    client_factory: Callable[[str], ContextManager],
    out_dir: Path,
) -> list[BakeoffResult]:
    results: list[BakeoffResult] = []
    for engine in dict.fromkeys(v.engine for v in voices):
        engine_voices = [v for v in voices if v.engine == engine]
        todo = [(v, s) for v in engine_voices for s in samples
                if not (Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav").exists()]
        for v in engine_voices:
            for s in samples:
                wav = Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav"
                if wav.exists():
                    results.append(BakeoffResult(engine, v.slug, s.sample_id, True, str(wav), None, 0.0, None))
        if not todo:
            continue
        with client_factory(engine) as client:
            for v, s in todo:
                wav = Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav"
                part = wav.with_name(f"{s.sample_id}.part.wav")
                wav.parent.mkdir(parents=True, exist_ok=True)
                text, params = render_request(engine, s.text, EmotionTag.from_dict(s.emotion))
                started = time.perf_counter()
                resp = client.synth(SynthRequest(
                    id=f"{engine}/{v.slug}/{s.sample_id}", text=text, out_path=str(part),
                    voice=v.voice, reference=v.reference, params=params,
                ))
                seconds = time.perf_counter() - started
                if resp.ok:
                    part.replace(wav)
                    results.append(BakeoffResult(engine, v.slug, s.sample_id, True, str(wav), resp.duration, seconds, None))
                else:
                    part.unlink(missing_ok=True)
                    results.append(BakeoffResult(engine, v.slug, s.sample_id, False, None, None, seconds, resp.error))
    return results


def write_sheet(samples: Sequence[Sample], results: Sequence[BakeoffResult], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    by_key = {(r.engine, r.voice_slug, r.sample_id): r for r in results}
    columns = sorted({(r.engine, r.voice_slug) for r in results})
    esc = html.escape
    head = "".join(f"<th>{esc(e)}<br><small>{esc(v)}</small></th>" for e, v in columns)
    rows = []
    for s in samples:
        cells = []
        for e, v in columns:
            r = by_key.get((e, v, s.sample_id))
            if r and r.ok and r.wav:
                src = Path(r.wav).resolve().relative_to(out_dir.resolve()).as_posix()
                cells.append(f'<td><audio controls preload="none" src="{esc(src)}"></audio></td>')
            else:
                cells.append(f"<td>– {esc(r.error) if r and r.error else ''}</td>")
        emo = s.emotion.get("emotion", "neutral")
        events = ", ".join(ev["tag"] for ev in s.emotion.get("events", []))
        rows.append(f"<tr><td><b>{esc(s.bucket)}</b><br>{esc(s.text)}<br><small>{esc(emo)} {esc(events)} · {esc(s.source)}/{esc(s.key)}</small></td>{''.join(cells)}</tr>")
    summary = []
    for e, v in columns:
        timed = [r for r in results if (r.engine, r.voice_slug) == (e, v) and r.ok and r.duration]
        dur = sum(r.duration for r in timed)
        sec = sum(r.seconds for r in timed)
        rtf = f"{sec / dur:.2f}" if dur else "–"
        summary.append(f"<tr><td>{esc(e)} / {esc(v)}</td><td>{dur:.1f} s</td><td>{sec:.1f} s</td><td>{rtf}</td></tr>")
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>DrovaVoice Hörtest</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}audio{{width:220px}}</style>
</head><body><h1>DrovaVoice Hörtest</h1>
<h2>Geschwindigkeit</h2><table><tr><th>Engine / Stimme</th><th>Audio</th><th>Rechenzeit</th><th>Echtzeitfaktor</th></tr>{''.join(summary)}</table>
<h2>Zeilen</h2><table><tr><th>Zeile</th>{head}</tr>{''.join(rows)}</table></body></html>"""
    path = out_dir / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
