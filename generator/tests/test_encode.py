import shutil
import wave
import math
import struct

import pytest

from drova_voice.emotions import EmotionTag
from drova_voice.encode import (build_filter, encode_one, ffmpeg_command, find_tools, probe_duration, rel_audio_path,
                                run_encode)
from drova_voice.ids import audio_filename
from drova_voice.lines import Line

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


def line(key="Plh_1", category="dialog"):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor="Mira", category=category, generic=False, raw="x", speech="x", stage=(), skip=None)


def sine_wav(path, seconds=1.0, lead_silence=0.3, rate=22050):
    frames = []
    for i in range(int(rate * (lead_silence + seconds))):
        v = 0 if i < rate * lead_silence else int(8000 * math.sin(2 * math.pi * 220 * i / rate))
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
    assert "silenceremove" in base and "loudnorm=I=-16" in base and "volume=" not in base
    assert build_filter(["whisper"]).endswith("volume=-6dB")
    assert build_filter(["drunk"]) == base  # unbekannte Hinweise ändern nichts


def test_ffmpeg_command_shape(tmp_path):
    cmd = ffmpeg_command("ffmpeg", tmp_path / "a.wav", tmp_path / "a.ogg", [])
    assert cmd[0] == "ffmpeg" and "libvorbis" in cmd and cmd[cmd.index("-ac") + 1] == "1" and cmd[-1].endswith("a.ogg")


def test_find_tools_reports_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr("drova_voice.encode.shutil.which", lambda name: None)
    with pytest.raises(ValueError, match="ffmpeg"):
        find_tools()


@needs_ffmpeg
def test_encode_one_trims_silence_and_is_resumable(tmp_path):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, seconds=1.0, lead_silence=0.5)
    dst = tmp_path / "out" / "dialog" / "x.ogg"
    duration = encode_one(ffmpeg, ffprobe, wav, dst, [], "key1")
    assert dst.is_file() and 0.8 < duration < 1.3  # Stille vorn ist weg (vorher 1,5 s)
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
