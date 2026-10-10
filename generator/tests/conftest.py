"""Hänge-Schutz für Tests mit Worker-Subprozessen.

Aufrufe, die einen Worker starten oder mit ihm sprechen, laufen über das Fixture ``guarded`` in einem Daemon-Thread.
Kommt keine Antwort innerhalb GUARD_TIMEOUT, werden alle in diesem Test gestarteten Worker getötet und der Test scheitert.
Am Ende jedes Tests werden Reste getötet und ihre Pipes geschlossen.
"""
import subprocess
import threading

import pytest

import drova_voice.engines.client as client_mod

GUARD_TIMEOUT = 20


def _reap(proc) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        try:
            if pipe is not None:
                pipe.close()
        except OSError:
            pass


@pytest.fixture
def workers(monkeypatch):
    """Sammelt alle von einem Test gestarteten Worker; Teardown tötet und schließt Reste."""
    started = []
    real_popen = subprocess.Popen

    def capturing_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr(client_mod.subprocess, "Popen", capturing_popen)
    yield started
    for proc in started:
        _reap(proc)


@pytest.fixture
def guarded(workers):
    """Führt einen Aufruf ohne Hängen-Gefahr aus und gibt sein Ergebnis oder seine Ausnahme weiter."""

    def run(fn):
        outcome = {}

        def target():
            try:
                outcome["value"] = fn()
            except BaseException as e:  # noqa: BLE001 – wird unten im Testthread erneut geworfen
                outcome["error"] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(GUARD_TIMEOUT)
        if thread.is_alive():
            for proc in workers:
                proc.kill()
            pytest.fail(f"Worker antwortet nicht innerhalb von {GUARD_TIMEOUT} s")
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("value")

    return run
