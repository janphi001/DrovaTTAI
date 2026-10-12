"""Fish-Audio-Worker: ruft die Cloud-API auf. Nur Standardbibliothek, kein venv nötig."""
from __future__ import annotations

import http.client
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

API_URL = "https://api.fish.audio/v1/tts"
MODEL = os.environ.get("FISH_MODEL", "s2.1-pro-free")
_RETRY_STATUS = {429, 500, 502, 503, 504}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Folgt keiner Weiterleitung: der Authorization-Header darf nie an einen anderen Ort gehen."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _int_env(name: str, default: str) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        raise RuntimeError(f"{name} ist keine ganze Zahl") from None


def _float_env(name: str, default: str) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        raise RuntimeError(f"{name} ist keine Zahl") from None
    if not math.isfinite(value) or value < 0:
        raise RuntimeError(f"{name} muss eine endliche Zahl >= 0 sein")
    return value


def load() -> dict:
    key = os.environ.get("FISH_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FISH_API_KEY fehlt: den Schlüssel nur als Umgebungsvariable setzen (nie in Dateien oder ins Repo)")
    # Der Schlüssel selbst darf in keiner Meldung stehen – sonst landet er im Protokoll/Log.
    if any(ord(ch) > 127 for ch in key):
        raise RuntimeError("FISH_API_KEY enthält ungültige Zeichen (nur ASCII erlaubt)")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in key):
        raise RuntimeError("FISH_API_KEY enthält ungültige Zeichen (Leerzeichen oder Zeilenumbruch?)")
    return {
        "key": key,
        "url": os.environ.get("FISH_API_URL", API_URL),
        "model": os.environ.get("FISH_MODEL", MODEL),
        "attempts": max(1, _int_env("FISH_MAX_ATTEMPTS", "5")),
        "backoff": _float_env("FISH_BACKOFF_S", "2.0"),
    }


def _clean(cfg: dict, text: str) -> str:
    return text.replace(cfg["key"], "***")


def _retry_after(headers, default: float) -> float:
    try:
        value = float(headers.get("Retry-After"))
    except (TypeError, ValueError):
        return default
    if math.isnan(value):  # min() würde NaN zu 60 s machen – lieber den Backoff nehmen
        return default
    return max(0.0, min(60.0, value))


def _post(cfg: dict, body: dict) -> bytes:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(cfg["url"], data=data, method="POST", headers={
        "Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json", "model": cfg["model"]})
    last = "unbekannt"
    for attempt in range(cfg["attempts"]):
        wait = cfg["backoff"] * (2 ** attempt)
        try:
            with _OPENER.open(request, timeout=180) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                raise RuntimeError(f"Fish leitet um (HTTP {e.code}); nicht gefolgt") from None
            # Erst maskieren, dann kürzen: sonst bleibt ein Schlüssel, der über die Kürzungsgrenze reicht, als Präfix stehen.
            detail = _clean(cfg, e.read().decode("utf-8", "replace"))[:200]
            if e.code not in _RETRY_STATUS:
                raise RuntimeError(f"Fish lehnt die Anfrage ab (HTTP {e.code}): {detail}") from None
            last, wait = f"HTTP {e.code}", _retry_after(e.headers, wait)
        except http.client.HTTPException as e:  # Antwort bricht mitten im Body ab (IncompleteRead, BadStatusLine)
            last = type(e).__name__
        except OSError as e:  # Verbindungsfehler, Zeitüberschreitung
            last = type(e).__name__
        except Exception as e:  # noqa: BLE001 – z. B. ValueError/UnicodeEncodeError beim Header-Aufbau in http.client
            raise RuntimeError(f"Fish-Anfrage fehlgeschlagen: {_clean(cfg, str(e))}") from None
        if attempt < cfg["attempts"] - 1:
            time.sleep(wait)
    raise RuntimeError(f"Fish nicht erreichbar nach {cfg['attempts']} Versuchen (zuletzt {last})")


def synth(cfg: dict, req: dict) -> tuple[int, float]:
    if req.get("reference"):
        raise ValueError("Fish nutzt eine Stimmen-ID (voice = reference_id), keine lokale Referenz-WAV")
    body = {"text": req["text"], "format": "wav", "temperature": 0.7, "top_p": 0.7}
    if req.get("voice"):
        body["reference_id"] = req["voice"]
    audio = _post(cfg, body)
    out = Path(req["out_path"])
    out.write_bytes(audio)
    try:
        with wave.open(str(out), "rb") as w:
            rate, frames = w.getframerate(), w.getnframes()
    except (wave.Error, EOFError) as e:
        out.unlink(missing_ok=True)
        raise RuntimeError(f"Fish lieferte kein gültiges WAV: {e}") from None
    return rate, frames / rate


if __name__ == "__main__":
    serve("fish", f"fish-audio/{MODEL}", load, synth)
