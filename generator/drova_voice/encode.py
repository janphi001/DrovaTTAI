from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.emotions import EmotionTag
from drova_voice.ids import audio_filename
from drova_voice.jsonl import replace_with_retry
from drova_voice.lines import Line, emotion_id

_TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
SAMPLE_RATE = 48000  # loudnorm tastet intern auf 192 kHz hoch; ohne aresample vor und nach ihm kommt 192 kHz heraus
WHISPER_GAIN_DB = -6
VARIANT_RATE = 44100  # Rezept in casting/fish_voices.yaml ist auf 44,1 kHz gerechnet


def rel_audio_path(line: Line) -> str:
    folder = "player/default" if line.category == "player" else line.category
    return f"{folder}/{audio_filename(line.id)}"


def variant_filter(v) -> str:
    """Rezept aus casting/fish_voices.yaml: formant (Vokaltrakt) über die Abtastrate, pitch/tempo über rubberband."""
    return (f"aresample={VARIANT_RATE},asetrate={round(VARIANT_RATE * v.formant)},aresample={VARIANT_RATE},"
            f"rubberband=pitch={v.pitch / v.formant:g}:tempo={v.tempo / v.formant:g}:formant=preserved")


def build_filter(notes: Sequence[str], variant=None) -> str:
    # Stille vorn und hinten entfernen (hinten: Umkehren, vorn trimmen, zurückdrehen), dann auf -16 LUFS.
    # (aresample vor UND nach loudnorm: mit ffmpeg 7.0 bricht jede andere Stellung des Filters ab.)
    parts = [variant_filter(variant)] if variant is not None else []
    parts += [_TRIM, "areverse", _TRIM, "areverse", f"aresample={SAMPLE_RATE}", LOUDNORM, f"aresample={SAMPLE_RATE}"]
    if "whisper" in notes:  # *flüstert*: leiser (das "gehauchte" kommt später, falls der Hörtest es verlangt)
        parts.append(f"volume={WHISPER_GAIN_DB}dB")
    return ",".join(parts)


def ffmpeg_command(ffmpeg: str, src: Path, dst: Path, notes: Sequence[str], variant=None) -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", build_filter(notes, variant),
            "-ac", "1", "-c:a", "libvorbis", "-q:a", "4", str(dst)]


def find_tools() -> tuple[str, str]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("ffmpeg/ffprobe nicht gefunden (müssen im PATH liegen)")
    encoders = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, errors="replace")
    if "libvorbis" not in encoders.stdout:
        raise ValueError("Dieses ffmpeg kann kein OGG Vorbis (Encoder libvorbis fehlt)")
    return ffmpeg, ffprobe


def require_rubberband(ffmpeg: str) -> None:
    out = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace")
    if " rubberband " not in out.stdout:
        raise ValueError("Dieses ffmpeg hat den Filter 'rubberband' nicht; er wird für Stimmenvarianten gebraucht")


def probe_duration(ffprobe: str, path: Path) -> float:
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _stamp(key: str, notes: Sequence[str], variant=None) -> str:
    return f"{key}|{build_filter(notes, variant)}"


def encode_one(ffmpeg: str, ffprobe: str, wav: Path, dst: Path, notes: Sequence[str], key: str, variant=None) -> float:
    dst = Path(dst)
    stamp_file = dst.with_suffix(".stamp")
    stamp = _stamp(key, notes, variant)
    if dst.is_file() and stamp_file.is_file() and stamp_file.read_text(encoding="utf-8") == stamp:
        return probe_duration(ffprobe, dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(f"{dst.stem}.part.ogg")
    proc = subprocess.run(ffmpeg_command(ffmpeg, Path(wav), part, notes, variant), capture_output=True, text=True, errors="replace")
    if proc.returncode != 0 or not part.is_file():
        part.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg Exit-Code {proc.returncode}: {proc.stderr.strip()[:200]}")
    replace_with_retry(part, dst)
    stamp_file.write_text(stamp, encoding="utf-8")
    return probe_duration(ffprobe, dst)


def run_encode(lines: Sequence[Line], synth_rows: Mapping[str, dict], emotions: Mapping[str, EmotionTag],
               audio_dir: Path, workers: int = 4, variants: Mapping[str, object] | None = None) -> tuple[list[dict], list[str]]:
    ffmpeg, ffprobe = find_tools()
    if variants:
        require_rubberband(ffmpeg)
    todo = [(l, synth_rows[l.id]) for l in lines if not l.skip and l.id in synth_rows and synth_rows[l.id].get("ok")]

    def work(item):
        line, row = item
        wav = Path(row["wav"] or "")
        if not wav.is_file():
            return None, f"{line.id}: WAV fehlt ({wav})"
        tag = emotion_id(line)
        notes = emotions[tag].notes if tag in emotions else []
        rel = rel_audio_path(line)
        try:
            duration = encode_one(ffmpeg, ffprobe, wav, Path(audio_dir) / rel, notes, row["key"], (variants or {}).get(line.id))
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
