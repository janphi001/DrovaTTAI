"""Gemeinsame Schleife für Engine-Worker (JSON-Lines über stdin/stdout).

Nur stdlib: wird von Workern in fremden venvs importiert.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any, Callable


def serve(engine: str, model: str, load: Callable[[], Any], synth: Callable[[Any, dict], tuple[int, float]]) -> None:
    # Protokoll-Kanal auf eine eigene Kopie von fd 1 legen, danach fd 1 auf stderr umleiten:
    # Ausgaben von Bibliotheken – auch native (C-Ebene) – dürfen das Protokoll nicht stören.
    sys.stdout.flush()
    proto = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    def send(obj: dict) -> None:
        proto.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proto.flush()

    state = load()
    proto.write("\n")  # schließt eine angefangene Fremdzeile ab, damit die Ready-Zeile eine eigene Zeile bleibt
    send({"ready": True, "engine": engine, "model": model})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            send({"id": None, "ok": False, "error": f"Ungültiges JSON: {e}"})
            continue
        try:
            sample_rate, duration = synth(state, req)
            send({"id": req.get("id"), "ok": True, "out_path": req["out_path"],
                  "sample_rate": sample_rate, "duration": duration})
        except Exception as e:  # noqa: BLE001 – jeder Fehler wird gemeldet, der Worker lebt weiter
            traceback.print_exc()
            send({"id": req.get("id"), "ok": False, "error": f"{type(e).__name__}: {e}"})
