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
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    model._builtin_conds = model.conds  # eingebaute Stimme merken: generate(audio_prompt_path=...) überschreibt model.conds
    model._ref_conds = {}
    return model


def synth(model, req: dict) -> tuple[int, float]:
    import soundfile as sf

    params = req.get("params") or {}
    exaggeration = float(params.get("exaggeration", 0.5))
    reference = req.get("reference")
    if reference:
        # Jede Referenz nur einmal einbetten und der Anfrage zuordnen; sie darf nicht in die nächste Anfrage durchsickern.
        if reference not in model._ref_conds:
            model.prepare_conditionals(reference, exaggeration=exaggeration)
            model._ref_conds[reference] = model.conds
        model.conds = model._ref_conds[reference]
    else:
        model.conds = model._builtin_conds
    wav = model.generate(req["text"], language_id="de", exaggeration=exaggeration,
                         cfg_weight=float(params.get("cfg_weight", 0.5)))
    sf.write(req["out_path"], wav.squeeze(0).cpu().numpy(), model.sr)
    return int(model.sr), wav.shape[-1] / model.sr


if __name__ == "__main__":
    serve("chatterbox", MODEL, load, synth, warmup_text="Guten Tag, wie geht es dir?")
