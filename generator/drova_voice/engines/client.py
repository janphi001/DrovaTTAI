from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from drova_voice.engines.protocol import SynthRequest, SynthResponse

_MAX_NOISE_LINES = 1000


class EngineError(RuntimeError):
    pass


class EngineClient:
    def __init__(self, cmd: Sequence[str], cwd: str | Path | None = None):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
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
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict) and ("ready" in obj or "ok" in obj):
                    return obj
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
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self._proc.kill()

    def __enter__(self) -> "EngineClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def worker_command(workers_dir: Path, engine: str) -> list[str]:
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
