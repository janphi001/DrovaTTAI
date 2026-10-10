"""Fake-Engine für Tests: schreibt einen Sinuston, Länge abhängig von der Textlänge."""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

RATE = 22050


def load():
    print("fake: lade Modell ... (dieser Text muss auf stderr landen)")
    return None


def synth(_state, req: dict) -> tuple[int, float]:
    text = req["text"]
    if "FAIL" in text:
        raise RuntimeError("absichtlicher Fehler")
    print(f"fake: synth {text!r}")
    duration = max(0.2, 0.05 * len(text))
    frames = int(RATE * duration)
    with wave.open(req["out_path"], "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / RATE))) for i in range(frames)))
    return RATE, frames / RATE


if __name__ == "__main__":
    serve("fake", "sine-1", load, synth)
