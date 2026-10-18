"""Gemeinsame Schleife für Engine-Worker (JSON-Lines über stdin/stdout).

Nur stdlib: wird von Workern in fremden venvs importiert.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from typing import Any, Callable


def _clear_output(path: str) -> str | None:
    """Entfernt eine alte Ausgabedatei, damit nur prüft, was dieser Aufruf schreibt. Gibt bei Fehler eine Meldung zurück."""
    try:
        os.remove(path)
    except FileNotFoundError:
        return None
    except OSError as e:
        return f"Alte Ausgabedatei konnte nicht entfernt werden: {path} ({e})"
    return None


def _warm_up(state: Any, synth: Callable[[Any, dict], tuple[int, float]], text: str) -> None:
    """Ein kurzer Satz vor der Ready-Zeile: CUDA-Kernel und Caches werden warm, bevor gemessen wird."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            synth(state, {"id": "warmup", "text": text, "out_path": os.path.join(tmp, "warmup.wav")})
    except Exception:  # noqa: BLE001 – Aufwärmen ist nur eine Optimierung
        traceback.print_exc()


def _http_attempts(state: Any) -> dict:
    """Nur die POST-Zählung des Fish-Workers. Der Zustand selbst (samt Schlüssel) geht nicht raus."""
    if isinstance(state, dict):
        attempts = state.get("http_attempts")
        if isinstance(attempts, int) and not isinstance(attempts, bool) and attempts >= 0:
            return {"http_attempts": attempts}
    return {}


def serve(engine: str, model: str, load: Callable[[], Any], synth: Callable[[Any, dict], tuple[int, float]],
          warmup_text: str | None = None) -> None:
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

    try:
        state = load()
    except Exception as e:  # noqa: BLE001 – der Grund soll beim Client ankommen, nicht nur im stderr-Rauschen
        traceback.print_exc()
        proto.write("\n")
        send({"ready": False, "engine": engine, "model": model, "error": f"{type(e).__name__}: {e}"})
        sys.exit(1)
    if warmup_text:
        _warm_up(state, synth, warmup_text)
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
        if not isinstance(req, dict):
            send({"id": None, "ok": False, "error": "Anfrage ist kein JSON-Objekt"})
            continue
        try:
            out_path = req["out_path"]
            problem = _clear_output(out_path)
            if problem:
                send({"id": req.get("id"), "ok": False, "error": problem})
                continue
            sample_rate, duration = synth(state, req)
            if not (os.path.isfile(out_path) and os.path.getsize(out_path) > 0):
                send({"id": req.get("id"), "ok": False, "error": f"Keine Audiodatei geschrieben: {out_path}"})
                continue
            if not duration > 0:
                send({"id": req.get("id"), "ok": False, "error": f"Leeres Audio (Dauer 0): {out_path}"})
                continue
            send({"id": req.get("id"), "ok": True, "out_path": out_path,
                  "sample_rate": sample_rate, "duration": duration, **_http_attempts(state)})
        except Exception as e:  # noqa: BLE001 – jeder Fehler wird gemeldet, der Worker lebt weiter
            traceback.print_exc()
            send({"id": req.get("id"), "ok": False, "error": f"{type(e).__name__}: {e}", **_http_attempts(state)})
