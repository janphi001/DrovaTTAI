from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

MODEL = "KittenML/kitten-tts-2"


def load():
    from kittenml import KittenTTS
    return KittenTTS(MODEL)


def synth(model, req: dict) -> tuple[int, float]:
    import soundfile as sf

    kwargs = {"normalize": False}
    if req.get("reference"):
        kwargs["reference"] = req["reference"]
    else:
        kwargs["voice"] = req.get("voice") or "German"
    audio = model.generate(req["text"], **kwargs)
    sf.write(req["out_path"], audio, model.sample_rate)
    return int(model.sample_rate), len(audio) / model.sample_rate


if __name__ == "__main__":
    serve("kitten", MODEL, load, synth)
