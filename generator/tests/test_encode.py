import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from drova_voice.emotions import EmotionTag
from drova_voice.encode import (build_filter, encode_one, ffmpeg_command, find_tools, probe_duration, rel_audio_path,
                                require_rubberband, run_encode, variant_filter)
from drova_voice.fish_voices import FishVariant
from drova_voice.ids import audio_filename
from drova_voice.lines import Line
from ffmpeg_marks import needs_rubberband

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


def line(key="Plh_1", category="dialog"):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor="Mira", category=category, generic=False, raw="x", speech="x", stage=(), skip=None)


def sine_wav(path, seconds=1.0, lead_silence=0.3, rate=22050, trail_silence=0.0):
    frames = []
    for i in range(int(rate * (lead_silence + seconds + trail_silence))):
        v = 0 if (i < rate * lead_silence or i >= rate * (lead_silence + seconds)) else int(8000 * math.sin(2 * math.pi * 220 * i / rate))
        frames.append(struct.pack("<h", v))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(frames))


def test_rel_audio_path_by_category():
    l = line("Plh_1")
    assert rel_audio_path(l) == f"dialog/{audio_filename(l.id)}"
    p = line("Plh_2", "player")
    assert rel_audio_path(p) == f"player/default/{audio_filename(p.id)}"
    assert rel_audio_path(line("Plh_3", "bark")).startswith("bark/")


def test_filter_chain_and_whisper():
    base = build_filter([])
    assert "silenceremove" in base and "loudnorm=I=-16" in base and ":linear=true" in base and "volume=" not in base
    assert "aresample=48000,loudnorm=" in base
    after = base.split("loudnorm", 1)[1].split(",", 1)[1]
    assert after.startswith("aresample=48000")  # aresample bleibt direkt vor und nach loudnorm
    assert build_filter(["whisper"]).endswith("volume=-6dB")
    assert build_filter(["drunk"]) == base  # unbekannte Hinweise ändern nichts


def test_ffmpeg_command_shape(tmp_path):
    cmd = ffmpeg_command("ffmpeg", tmp_path / "a.wav", tmp_path / "a.ogg", [])
    assert cmd[0] == "ffmpeg" and "libvorbis" in cmd and cmd[cmd.index("-ac") + 1] == "1" and cmd[-1].endswith("a.ogg")


def test_find_tools_reports_ffmpeg_without_vorbis(monkeypatch):
    class Result:
        stdout = " A..... aac  AAC (Advanced Audio Coding)\n"

    monkeypatch.setattr("drova_voice.encode.shutil.which", lambda name: name)
    monkeypatch.setattr("drova_voice.encode.subprocess.run", lambda *a, **k: Result())
    with pytest.raises(ValueError, match="libvorbis"):
        find_tools()


@needs_ffmpeg
def test_output_is_48khz_mono_vorbis(tmp_path):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, rate=44100)
    dst = tmp_path / "x.ogg"
    encode_one(ffmpeg, ffprobe, wav, dst, [], "k")
    info = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels",
                           "-of", "csv=p=0", str(dst)], capture_output=True, text=True, check=True).stdout.strip()
    assert info == "vorbis,48000,1"


def test_find_tools_reports_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr("drova_voice.encode.shutil.which", lambda name: None)
    with pytest.raises(ValueError, match="ffmpeg"):
        find_tools()


@needs_ffmpeg
def test_encode_one_trims_silence_and_is_resumable(tmp_path):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, seconds=1.0, lead_silence=0.5, trail_silence=0.5)
    dst = tmp_path / "out" / "dialog" / "x.ogg"
    duration = encode_one(ffmpeg, ffprobe, wav, dst, [], "key1")
    assert dst.is_file() and 0.8 < duration < 1.3  # Stille vorn und hinten ist weg (vorher 2,0 s)
    stamp_before = dst.stat().st_mtime_ns
    assert encode_one(ffmpeg, ffprobe, wav, dst, [], "key1") == pytest.approx(duration, abs=0.01)
    assert dst.stat().st_mtime_ns == stamp_before  # nichts neu kodiert
    encode_one(ffmpeg, ffprobe, wav, dst, ["whisper"], "key1")  # anderer Hinweis -> neu kodiert
    assert dst.stat().st_mtime_ns != stamp_before
    assert list((tmp_path / "out" / "dialog").glob("*.part.ogg")) == []
    assert probe_duration(ffprobe, dst) > 0


@needs_ffmpeg
def test_run_encode_collects_rows_and_errors(tmp_path):
    wav = tmp_path / "a.wav"
    sine_wav(wav)
    lines = [line("Plh_1"), line("Plh_2"), line("Plh_3")]
    synth_rows = {"T|P|Plh_1": {"id": "T|P|Plh_1", "ok": True, "wav": str(wav), "key": "k1"},
                  "T|P|Plh_2": {"id": "T|P|Plh_2", "ok": True, "wav": str(tmp_path / "weg.wav"), "key": "k2"}}
    rows, errors = run_encode(lines, synth_rows, {"T|P|Plh_1": EmotionTag("neutral", 0.0, source="llm")},
                              tmp_path / "audio", workers=2)
    assert [r["id"] for r in rows] == ["T|P|Plh_1"] and rows[0]["rel"] == rel_audio_path(lines[0])
    assert (tmp_path / "audio" / rows[0]["rel"]).is_file()
    assert len(errors) == 1 and "Plh_2" in errors[0]  # WAV fehlt; Plh_3 hat gar keine Synth-Zeile und zählt nicht als Fehler


def variant(pitch=1.0, formant=2.0, tempo=1.0):
    return FishVariant("v", "lena", "V", "f", None, None, pitch, formant, tempo)


def test_variant_filter_follows_the_recipe():
    assert variant_filter(variant()) == ("aresample=44100,asetrate=88200,aresample=44100,"
                                         "rubberband=pitch=0.5:tempo=0.5:formant=preserved")


def test_filter_with_variant_starts_with_the_recipe():
    assert build_filter([], variant()).startswith(variant_filter(variant()) + ",silenceremove")
    assert build_filter([]) == build_filter([], None)


def test_require_rubberband_reports_a_missing_filter(monkeypatch):
    class Result:
        stdout = " ... A->A       atempo             Adjust audio tempo.\n"

    monkeypatch.setattr("drova_voice.encode.subprocess.run", lambda *a, **k: Result())
    with pytest.raises(ValueError, match="rubberband"):
        require_rubberband("ffmpeg")


def test_require_rubberband_accepts_the_filter(monkeypatch):
    class Result:
        stdout = " ..C rubberband        A->A       Apply time-stretching and pitch-shifting.\n"

    monkeypatch.setattr("drova_voice.encode.subprocess.run", lambda *a, **k: Result())
    assert require_rubberband("ffmpeg") is None


def test_run_encode_with_a_variant_checks_rubberband_before_anything_else(tmp_path, monkeypatch):
    def missing(ffmpeg):
        raise ValueError("ffmpeg ohne rubberband")

    monkeypatch.setattr("drova_voice.encode.find_tools", lambda: ("ffmpeg", "ffprobe"))
    monkeypatch.setattr("drova_voice.encode.require_rubberband", missing)
    with pytest.raises(ValueError, match="rubberband"):
        run_encode([line()], {"T|P|Plh_1": {"id": "T|P|Plh_1", "ok": True, "wav": "x.wav", "key": "k"}}, {}, tmp_path, 1,
                   {"T|P|Plh_1": variant()})


@needs_rubberband
def test_encode_one_applies_the_variant_and_restamps(tmp_path):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, seconds=1.0, lead_silence=0.0, rate=44100)
    dst = tmp_path / "out" / "x.ogg"
    plain = encode_one(ffmpeg, ffprobe, wav, dst, [], "k")
    before = dst.stat().st_mtime_ns
    slow = encode_one(ffmpeg, ffprobe, wav, dst, [], "k", variant(pitch=1.0, formant=1.0, tempo=0.5))
    assert dst.stat().st_mtime_ns != before  # anderes Rezept -> neu kodiert
    assert slow > plain * 1.5  # Tempo 0.5 dehnt die Zeit


def _stamp(dst):
    return json.loads(dst.with_suffix(".stamp").read_text(encoding="utf-8"))


def test_cache_hit_does_not_run_ffprobe(tmp_path, monkeypatch):
    dst = tmp_path / "a.ogg"
    dst.write_bytes(b"OggS")
    recipe = build_filter([])
    dst.with_suffix(".stamp").write_text(json.dumps({"duration": 1.25, "filter": recipe, "key": "k"}) + "\n", encoding="utf-8")

    def boom(*_a, **_k):
        raise AssertionError("subprocess")

    monkeypatch.setattr("drova_voice.encode.subprocess.run", boom)
    assert encode_one("ffmpeg", "ffprobe", tmp_path / "in.wav", dst, [], "k") == pytest.approx(1.25)


def test_legacy_text_stamp_is_probed_once(tmp_path, monkeypatch):
    dst = tmp_path / "a.ogg"
    dst.write_bytes(b"OggS")
    recipe = build_filter([])
    dst.with_suffix(".stamp").write_text(f"k|{recipe}", encoding="utf-8")
    calls = []

    class Result:
        returncode = 0
        stdout = "1.5\n"
        stderr = ""

    def fake(cmd, **_k):
        calls.append(list(cmd))
        assert cmd[0] == "ffprobe"
        return Result()

    monkeypatch.setattr("drova_voice.encode.subprocess.run", fake)
    assert encode_one("ffmpeg", "ffprobe", tmp_path / "in.wav", dst, [], "k") == pytest.approx(1.5)
    assert len(calls) == 1 and _stamp(dst)["duration"] == pytest.approx(1.5)
    assert encode_one("ffmpeg", "ffprobe", tmp_path / "in.wav", dst, [], "k") == pytest.approx(1.5)
    assert len(calls) == 1


def test_fresh_encode_applies_measured_linear_loudnorm_and_then_skips_ffprobe(tmp_path, monkeypatch):
    wav = tmp_path / "in.wav"
    wav.write_bytes(b"RIFF")
    dst = tmp_path / "out" / "a.ogg"
    calls = []

    class Result:
        def __init__(self, stdout="", stderr="", code=0):
            self.returncode = code
            self.stdout = stdout
            self.stderr = stderr

    def fake(cmd, **_k):
        calls.append(list(cmd))
        if cmd[0] == "ffprobe":
            return Result(stdout="0.42\n")
        audio_filter = cmd[cmd.index("-af") + 1]
        if "print_format=json" in audio_filter:
            return Result(stderr="\n".join([
                "{",
                '  "input_i" : "-20.00",',
                '  "input_tp" : "-4.00",',
                '  "input_lra" : "1.00",',
                '  "input_thresh" : "-30.00",',
                '  "target_offset" : "0.10"',
                "}",
            ]))
        assert "measured_I=-20.00" in audio_filter and "linear=true" in audio_filter and "apad" not in audio_filter
        assert audio_filter.index("aresample=48000") < audio_filter.index("loudnorm")
        Path(cmd[-1]).write_bytes(b"OggS")
        return Result()

    monkeypatch.setattr("drova_voice.encode.subprocess.run", fake)
    assert encode_one("ffmpeg", "ffprobe", wav, dst, [], "k") == pytest.approx(0.42)
    assert _stamp(dst)["loudnorm"]["input_i"] == "-20.00"
    calls.clear()
    assert encode_one("ffmpeg", "ffprobe", wav, dst, [], "k") == pytest.approx(0.42)
    assert calls == []


def _integrated_lufs(ffmpeg, path):
    proc = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True)
    text = proc.stderr
    start = text.rfind("Integrated loudness:")
    assert start >= 0, text[-400:]
    for line in text[start:].splitlines():
        if "I:" in line and "LUFS" in line:
            return float(line.split()[1])
    raise AssertionError(text[start:start + 200])


@needs_ffmpeg
def test_short_clip_stays_short_and_near_minus_16_lufs(tmp_path, monkeypatch):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, seconds=0.45, lead_silence=0.0, rate=48000)
    dst = tmp_path / "out" / "short.ogg"
    duration = encode_one(ffmpeg, ffprobe, wav, dst, [], "k")
    assert 0.2 < duration < 1.2  # nicht auf 3 s aufgefüllt
    assert _integrated_lufs(ffmpeg, dst) == pytest.approx(-16.0, abs=1.0)
    stamp = _stamp(dst)
    assert "linear=true" in stamp["filter"] and "aresample=48000,loudnorm=" in stamp["filter"]
    assert "input_i" in stamp["loudnorm"]

    def boom(*_a, **_k):
        raise AssertionError("subprocess")

    monkeypatch.setattr("drova_voice.encode.subprocess.run", boom)
    assert encode_one(ffmpeg, ffprobe, wav, dst, [], "k") == pytest.approx(duration)
