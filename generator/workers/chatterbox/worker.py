from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

MODEL = "ResembleAI/chatterbox-multilingual"


def load():
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return ChatterboxMultilingualTTS.from_pretrained(device=device)


def synth(model, req: dict) -> tuple[int, float]:
    import torchaudio

    params = req.get("params") or {}
    kwargs = {
        "language_id": "de",
        "exaggeration": float(params.get("exaggeration", 0.5)),
        "cfg_weight": float(params.get("cfg_weight", 0.5)),
    }
    if req.get("reference"):
        kwargs["audio_prompt_path"] = req["reference"]
    wav = model.generate(req["text"], **kwargs)
    torchaudio.save(req["out_path"], wav.cpu(), model.sr)
    return int(model.sr), wav.shape[-1] / model.sr


if __name__ == "__main__":
    serve("chatterbox", MODEL, load, synth)
