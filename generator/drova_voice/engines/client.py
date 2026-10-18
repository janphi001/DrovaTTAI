from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.engines.protocol import SynthRequest, SynthResponse

_MAX_NOISE_LINES = 1000
_READY_MARKER = '{"ready"'
_CLOSE_TIMEOUT_S = 30
_ENGINE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class EngineError(RuntimeError):
    pass


def cache_env(cache_dir: Path, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Modell-Caches der Engines ins Projekt legen (sonst landen GB auf C:). Vom Nutzer gesetzte Werte bleiben."""
    base = os.environ if base is None else base
    wanted = {"HF_HOME": "hf", "TTS_HOME": "tts", "PKUSEG_HOME": "pkuseg"}
    return {name: str(Path(cache_dir) / sub) for name, sub in wanted.items() if name not in base}


def _json_dict(text: str) -> dict | None:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


class EngineClient:
    def __init__(self, cmd: Sequence[str], cwd: str | Path | None = None, env: Mapping[str, str] | None = None):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", **(env or {}))
        self._proc = subprocess.Popen(
            list(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=cwd, env=env,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        try:
            hello = self._read()
            if not hello.get("ready"):
                raise EngineError(f"Worker nicht bereit: {hello}")
        except BaseException:
            self.close()  # Worker nicht verwaist zurücklassen
            raise
        self.engine = hello.get("engine")
        self.model = hello.get("model")

    def _read(self) -> dict:
        for _ in range(_MAX_NOISE_LINES):
            line = self._proc.stdout.readline()
            if not line:
                raise EngineError(f"Worker beendet (Exit-Code {self._proc.poll()})")
            line = line.strip()
            obj = _json_dict(line)
            if obj is None and _READY_MARKER in line:
                # Fremdtext (auch einer, der mit "{" beginnt) direkt vor der Ready-Zeile: nur den Präfix als Lärm
                # weiterleiten, ab der Ready-Zeile parsen.
                cut = line.index(_READY_MARKER)
                if cut:
                    print(f"[worker stdout] {line[:cut]}", file=sys.stderr)
                line = line[cut:]
                obj = _json_dict(line)
            if obj is not None and ("ready" in obj or "ok" in obj):
                return obj
            if line:  # Leerzeilen sind kein Lärm
                print(f"[worker stdout] {line}", file=sys.stderr)
        raise EngineError("Worker liefert kein gültiges Protokoll")

    def synth(self, req: SynthRequest) -> SynthResponse:
        try:
            self._proc.stdin.write(req.to_json() + "\n")
            self._proc.stdin.flush()
        except OSError as e:
            raise EngineError(f"Worker nimmt keine Anfragen mehr an: {e}") from e
        resp = SynthResponse.from_dict(self._read())
        if resp.id != req.id:
            raise EngineError(f"Antwort-ID {resp.id!r} passt nicht zu Anfrage {req.id!r}")
        return resp

    def close(self) -> None:
        # Immer: Eingabe schließen, auf Ende warten, notfalls töten, dann Ausgabe schließen (auch bei beendetem Worker).
        try:
            self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=_CLOSE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        finally:
            self._proc.stdout.close()

    def __enter__(self) -> "EngineClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def worker_command(workers_dir: Path, engine: str) -> list[str]:
    # Nur ein Ordnername: kein Pfad, damit die Engine nicht außerhalb von workers/ startet.
    if not isinstance(engine, str) or _ENGINE_NAME.fullmatch(engine) is None:
        raise EngineError("Unbekannte Engine")
    wdir = Path(workers_dir) / engine
    script = wdir / "worker.py"
    if not script.exists():
        raise EngineError(f"Unbekannte Engine '{engine}': {script} fehlt")
    py = wdir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if py.exists():
        return [str(py), str(script)]
    if (wdir / "requirements.txt").exists():
        raise EngineError(f"venv für '{engine}' fehlt: {py}. Siehe {wdir / 'README.md'}")
    return [sys.executable, str(script)]
