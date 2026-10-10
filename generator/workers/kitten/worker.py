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
    preset = (req.get("params") or {}).get("preset")
    if preset:
        kwargs["preset"] = preset
    if req.get("reference"):
        transcript = Path(req["reference"]).with_suffix(".txt")
        if not transcript.is_file():
            # Ohne Text transkribiert Kitten die Referenz selbst: Whisper-large-v3 (ca. 3 GB Download), fest auf Englisch.
            raise ValueError(f"Referenztext fehlt: {transcript} (ohne ihn würde Kitten Whisper laden); `bakeoff refs` schreibt ihn mit")
        kwargs["reference"] = req["reference"]
        kwargs["reference_text"] = transcript.read_text(encoding="utf-8").strip()
    else:
        kwargs["voice"] = req.get("voice") or "German"
    audio = model.generate(req["text"], **kwargs)
    sf.write(req["out_path"], audio, model.sample_rate)
    return int(model.sample_rate), len(audio) / model.sample_rate


if __name__ == "__main__":
    serve("kitten", MODEL, load, synth, warmup_text="Guten Tag, wie geht es dir?")
