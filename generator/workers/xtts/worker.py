from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve

MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"


def load():
    if os.environ.get("COQUI_TOS_AGREED") != "1":
        raise RuntimeError("CPML nicht bestätigt: COQUI_TOS_AGREED=1 setzen (siehe README)")
    import torch
    from TTS.api import TTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return TTS(MODEL).to(device)


def synth(tts, req: dict) -> tuple[int, float]:
    import numpy as np
    import soundfile as sf

    kwargs = {"language": "de"}
    if req.get("reference"):
        kwargs["speaker_wav"] = req["reference"]
    else:
        kwargs["speaker"] = req.get("voice") or "Ana Florence"
    wav = np.asarray(tts.tts(text=req["text"], **kwargs), dtype=np.float32)
    rate = int(tts.synthesizer.output_sample_rate)
    sf.write(req["out_path"], wav, rate)
    return rate, len(wav) / rate


if __name__ == "__main__":
    serve("xtts", MODEL, load, synth, warmup_text="Guten Tag, wie geht es dir?")
