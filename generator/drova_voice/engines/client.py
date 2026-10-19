from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Self

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


def _decode_stdout_line(raw: bytes) -> str | None:
    """Dekodiert eine fertige Zeile strikt. None: die Bytes sind kein UTF-8 und kein Protokoll.

    Erst die ganze Zeile, dann ein Decode. Ein Mehrbyte-Zeichen, das auf zwei
    Reads fiel, ist dann vollständig und wird nicht zu U+FFFD. Ungültige Bytes
    dürfen den JSON-Parser nicht erreichen, auch nicht als Ersatzzeichen.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        marker = _READY_MARKER.encode("ascii")
        cut = raw.find(marker)
        if cut > 0:
            try:
                suffix = raw[cut:].decode("utf-8")
            except UnicodeDecodeError:
                pass
            else:
                print(f"[worker stdout] {raw[:cut]!r}", file=sys.stderr)
                return suffix
        print(f"[worker stdout] {raw!r}", file=sys.stderr)
        return None


class _StdoutLines:
    """Sammelt Worker-stdout bis zum Zeilenende und dekodiert erst dann."""

    def __init__(self, raw):
        self._raw = raw
        self._pending = bytearray()

    def _pull(self) -> bytes:
        # Genau ein Read. Ein auffüllendes read() würde blockieren, sobald der
        # Worker nach der Zeile auf die nächste Anfrage wartet.
        buf = bytearray(4096)
        n = self._raw.readinto(buf)
        if not n:
            return b""
        return bytes(buf[:n])

    def readline(self) -> str | None:
        """Eine UTF-8-Zeile, '' bei Dateiende, None bei einer Zeile ohne gültiges UTF-8."""
        while True:
            newline_at = self._pending.find(b"\n")
            if newline_at == -1:
                chunk = self._pull()
                if not chunk:
                    if not self._pending:
                        return ""
                    raw = bytes(self._pending)
                    self._pending.clear()
                    return _decode_stdout_line(raw)
                self._pending.extend(chunk)
                continue
            raw = bytes(self._pending[: newline_at + 1])
            del self._pending[: newline_at + 1]
            return _decode_stdout_line(raw)


class EngineClient:
    def __init__(
        self,
        cmd: Sequence[str],
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
    ):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", **(env or {}))
        # Binär und ungepuffert. errors="replace" auf dem Text-Stream darf eine
        # unvollständige UTF-8-Sequenz nicht als U+FFFD in eine JSON-Zeile setzen.
        self._proc = subprocess.Popen(
            list(cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=cwd,
            env=env,
            bufsize=0,
        )
        self._stdout_lines = _StdoutLines(self._proc.stdout)
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
            line = self._stdout_lines.readline()
            if line is None:
                continue
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
            _write_all(self._proc.stdin, (req.to_json() + "\n").encode("utf-8"))
        except OSError as e:
            raise EngineError(f"Worker nimmt keine Anfragen mehr an: {e}") from e
        resp = SynthResponse.from_dict(self._read())
        if resp.id != req.id:
            raise EngineError(f"Antwort-ID {resp.id!r} passt nicht zu Anfrage {req.id!r}")
        return resp

    def close(self) -> None:
        # Immer: Eingabe schließen, auf Ende warten, notfalls töten, dann Ausgabe schließen (auch bei beendetem Worker).
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=_CLOSE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        finally:
            if self._proc.stdout is not None:
                self._proc.stdout.close()

    def __enter__(self) -> Self:
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


def _write_all(pipe, data: bytes) -> None:
    """Schreibt alles. Die Pipe ist ungepuffert (bufsize=0), write() darf dort kürzer ausfallen."""
    view = memoryview(data)
    while view:
        written = pipe.write(view)
        if written is None:
            raise OSError("Pipe nimmt gerade nichts an")
        view = view[written:]
