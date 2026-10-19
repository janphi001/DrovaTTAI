from __future__ import annotations

import json
import math
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from drova_voice.emotions import EmotionTag
from drova_voice.ids import audio_filename
from drova_voice.jsonl import replace_with_retry
from drova_voice.lines import Line, emotion_id

_TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
SAMPLE_RATE = 48000  # loudnorm tastet intern auf 192 kHz hoch; ohne aresample vor und nach ihm kommt 192 kHz heraus
WHISPER_GAIN_DB = -6
VARIANT_RATE = 44100  # Rezept in casting/fish_voices.yaml ist auf 44,1 kHz gerechnet
# loudnorm akzeptiert diese Messwerte nur in diesen Bereichen; außerhalb (z. B. -inf bei Stille) fällt der Lauf auf
# den einstufigen Filter zurück.
_MEASURED_RANGE = {
    "input_i": (-99.0, 0.0),
    "input_tp": (-99.0, 99.0),
    "input_lra": (0.0, 99.0),
    "input_thresh": (-99.0, 0.0),
    "target_offset": (-99.0, 99.0),
}


def rel_audio_path(line: Line) -> str:
    folder = "player/default" if line.category == "player" else line.category
    return f"{folder}/{audio_filename(line.id)}"


def variant_filter(v) -> str:
    """Rezept aus casting/fish_voices.yaml: formant (Vokaltrakt) über die Abtastrate, pitch/tempo über rubberband."""
    return (
        f"aresample={VARIANT_RATE},asetrate={round(VARIANT_RATE * v.formant)},aresample={VARIANT_RATE},"
        f"rubberband=pitch={v.pitch / v.formant:g}:tempo={v.tempo / v.formant:g}:formant=preserved"
    )


def _front(variant=None) -> list[str]:
    # Stille vorn und hinten entfernen (hinten: Umkehren, vorn trimmen, zurückdrehen).
    parts = [variant_filter(variant)] if variant is not None else []
    parts += [_TRIM, "areverse", _TRIM, "areverse"]
    return parts


def build_filter(notes: Sequence[str], variant=None) -> str:
    # Rezept für den Stempel. linear=true: der echte Lauf ist zweistufig (gemessen, dann konstante Verstärkung).
    # (aresample vor UND nach loudnorm: mit ffmpeg 7.0 bricht jede andere Stellung des Filters ab.)
    # Kurze Clips bleiben ungefüllt: Stille auf 3 s aufzufüllen zieht die gemessene Lautheit nach unten,
    # nach dem Zurückschneiden liegt die Zeile über dem Ziel. ffmpeg 6 misst unter 3 s bereits linear.
    parts = _front(variant) + [
        f"aresample={SAMPLE_RATE}",
        f"{LOUDNORM}:linear=true",
        f"aresample={SAMPLE_RATE}",
    ]
    if (
        "whisper" in notes
    ):  # *flüstert*: leiser (das "gehauchte" kommt später, falls der Hörtest es verlangt)
        parts.append(f"volume={WHISPER_GAIN_DB}dB")
    return ",".join(parts)


def _linear_loudnorm(measured: Mapping[str, str]) -> str:
    return (
        f"{LOUDNORM}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true"
    )


def encode_filter(
    notes: Sequence[str], variant=None, measured: Mapping[str, str] | None = None
) -> str:
    loud = _linear_loudnorm(measured) if measured else LOUDNORM
    parts = _front(variant) + [f"aresample={SAMPLE_RATE}", loud, f"aresample={SAMPLE_RATE}"]
    if "whisper" in notes:
        parts.append(f"volume={WHISPER_GAIN_DB}dB")
    return ",".join(parts)


def _measure_filter(variant=None) -> str:
    return ",".join(_front(variant) + [f"aresample={SAMPLE_RATE}", f"{LOUDNORM}:print_format=json"])


def ffmpeg_command(
    ffmpeg: str,
    src: Path,
    dst: Path,
    notes: Sequence[str],
    variant=None,
    audio_filter: str | None = None,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-af",
        build_filter(notes, variant) if audio_filter is None else audio_filter,
        "-ac",
        "1",
        "-c:a",
        "libvorbis",
        "-q:a",
        "4",
        str(dst),
    ]


def find_tools() -> tuple[str, str]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("ffmpeg/ffprobe nicht gefunden (müssen im PATH liegen)")
    encoders = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if "libvorbis" not in encoders.stdout:
        raise ValueError("Dieses ffmpeg kann kein OGG Vorbis (Encoder libvorbis fehlt)")
    return ffmpeg, ffprobe


def require_rubberband(ffmpeg: str) -> None:
    out = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if " rubberband " not in out.stdout:
        raise ValueError(
            "Dieses ffmpeg hat den Filter 'rubberband' nicht; er wird für Stimmenvarianten gebraucht"
        )


def probe_duration(ffprobe: str, path: Path) -> float:
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def _usable_measured(data: object) -> dict[str, str] | None:
    if not isinstance(data, dict):
        return None
    measured: dict[str, str] = {}
    for name, (low, high) in _MEASURED_RANGE.items():
        raw = data.get(name)
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            return None
        text = str(raw).strip()
        try:
            number = float(text)
        except ValueError:
            return None
        if not math.isfinite(number) or not low <= number <= high:
            return None
        measured[name] = text
    return measured


def _parse_loudnorm(stderr: str) -> dict[str, str] | None:
    start, end = stderr.rfind("{"), stderr.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return _usable_measured(json.loads(stderr[start : end + 1]))
    except json.JSONDecodeError:
        return None


def _measure_loudnorm(ffmpeg: str, wav: Path, variant=None) -> dict[str, str] | None:
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(wav),
            "-af",
            _measure_filter(variant),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg Exit-Code {proc.returncode}: {proc.stderr.strip()[:200]}")
    return _parse_loudnorm(proc.stderr)


def _load_stamp(text: str) -> tuple[str, str, float] | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    key, recipe, duration = data.get("key"), data.get("filter"), data.get("duration")
    if not isinstance(key, str) or not isinstance(recipe, str):
        return None
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        return None
    return key, recipe, float(duration)


def _write_stamp(
    path: Path, key: str, recipe: str, duration: float, measured: Mapping[str, str] | None
) -> None:
    payload: dict[str, object] = {"duration": duration, "filter": recipe, "key": key}
    if measured:
        payload["loudnorm"] = dict(measured)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def _run_ffmpeg(
    ffmpeg: str, wav: Path, part: Path, notes: Sequence[str], variant, measured
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ffmpeg_command(ffmpeg, wav, part, notes, variant, encode_filter(notes, variant, measured)),
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )


def encode_one(
    ffmpeg: str, ffprobe: str, wav: Path, dst: Path, notes: Sequence[str], key: str, variant=None
) -> float:
    dst = Path(dst)
    stamp_file = dst.with_suffix(".stamp")
    recipe = build_filter(notes, variant)
    if dst.is_file() and stamp_file.is_file():
        raw = stamp_file.read_text(encoding="utf-8")
        cached = _load_stamp(raw)
        if cached is not None and cached[0] == key and cached[1] == recipe:
            return cached[2]
        # Alter Textstempel ohne Dauer: einmal messen, dann als JSON merken.
        if raw.strip() == f"{key}|{recipe}":
            duration = probe_duration(ffprobe, dst)
            _write_stamp(stamp_file, key, recipe, duration, None)
            return duration
    dst.parent.mkdir(parents=True, exist_ok=True)
    measured = _measure_loudnorm(ffmpeg, Path(wav), variant)
    part = dst.with_name(f"{dst.stem}.part.ogg")
    proc = _run_ffmpeg(ffmpeg, Path(wav), part, notes, variant, measured)
    if (proc.returncode != 0 or not part.is_file()) and measured:
        # Messwerte, die ffmpeg doch ablehnt: einmal ohne sie, einstufig.
        part.unlink(missing_ok=True)
        measured = None
        proc = _run_ffmpeg(ffmpeg, Path(wav), part, notes, variant, None)
    if proc.returncode != 0 or not part.is_file():
        part.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg Exit-Code {proc.returncode}: {proc.stderr.strip()[:200]}")
    replace_with_retry(part, dst)
    duration = probe_duration(ffprobe, dst)
    _write_stamp(stamp_file, key, recipe, duration, measured)
    return duration


def run_encode(
    lines: Sequence[Line],
    synth_rows: Mapping[str, dict],
    emotions: Mapping[str, EmotionTag],
    audio_dir: Path,
    workers: int = 4,
    variants: Mapping[str, object] | None = None,
) -> tuple[list[dict], list[str]]:
    ffmpeg, ffprobe = find_tools()
    if variants:
        require_rubberband(ffmpeg)
    todo = [
        (l, synth_rows[l.id])
        for l in lines
        if not l.skip and l.id in synth_rows and synth_rows[l.id].get("ok")
    ]

    def work(item):
        line, row = item
        wav = Path(row["wav"] or "")
        if not wav.is_file():
            return None, f"{line.id}: WAV fehlt ({wav})"
        tag = emotion_id(line)
        notes = emotions[tag].notes if tag in emotions else []
        rel = rel_audio_path(line)
        try:
            duration = encode_one(
                ffmpeg,
                ffprobe,
                wav,
                Path(audio_dir) / rel,
                notes,
                row["key"],
                (variants or {}).get(line.id),
            )
        except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as e:
            return None, f"{line.id}: {e}"
        return {"id": line.id, "rel": rel, "duration": round(duration, 3), "key": row["key"]}, None

    rows: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for row, error in pool.map(work, todo):
            if row:
                rows.append(row)
            if error:
                errors.append(error)
    return rows, errors
