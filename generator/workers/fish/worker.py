"""Fish-Audio-Worker: ruft die Cloud-API auf. Nur Standardbibliothek, kein venv nötig."""

from __future__ import annotations

import html
import http.client
import json
import math
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve

API_URL = "https://api.fish.audio/v1/tts"
MODEL_API_URL = "https://api.fish.audio/model"
# Dieselbe ID wie drova_voice.fish_model.DEFAULT_FISH_MODEL. Der Generator setzt FISH_MODEL immer selbst.
MODEL = os.environ.get("FISH_MODEL", "s2.1-pro-free")
_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_ERROR_BODY = 4096
REQUEST_TIMEOUT_S = 180.0
DEFAULT_MAX_ATTEMPTS = (
    2  # synth.py wiederholt die Qualität; zusammen höchstens wenige POSTs, nicht 5×3
)
MAX_HTTP_ATTEMPTS = 3
DEFAULT_DEADLINE_S = 240.0
_LANG = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")
_LATENCIES = ("normal", "balanced", "low")


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


def _bounded_attempts() -> int:
    return min(MAX_HTTP_ATTEMPTS, max(1, _int_env("FISH_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS))))


def _deadline() -> float:
    value = _float_env("FISH_DEADLINE_S", str(int(DEFAULT_DEADLINE_S)))
    if value <= 0:
        raise RuntimeError("FISH_DEADLINE_S muss größer als 0 sein")
    return value


def _unit_env(name: str, default: str) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        raise RuntimeError(f"{name} ist keine Zahl") from None
    if not math.isfinite(value) or not 0 < value <= 1:
        raise RuntimeError(f"{name} muss größer als 0 und höchstens 1 sein")
    return value


def load() -> dict:
    key = os.environ.get("FISH_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "FISH_API_KEY fehlt: den Schlüssel nur als Umgebungsvariable setzen (nie in Dateien oder ins Repo)"
        )
    # Der Schlüssel selbst darf in keiner Meldung stehen – sonst landet er im Protokoll/Log.
    if any(ord(ch) > 127 for ch in key):
        raise RuntimeError("FISH_API_KEY enthält ungültige Zeichen (nur ASCII erlaubt)")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in key):
        raise RuntimeError(
            "FISH_API_KEY enthält ungültige Zeichen (Leerzeichen oder Zeilenumbruch?)"
        )
    return {
        "key": key,
        "url": _check_url(os.environ.get("FISH_API_URL", API_URL), key),
        "model": os.environ.get("FISH_MODEL", MODEL),
        "attempts": _bounded_attempts(),
        "backoff": _float_env("FISH_BACKOFF_S", "2.0"),
        "deadline": _deadline(),
        "language": os.environ.get("FISH_LANGUAGE", "de").strip() or "de",
        "latency": os.environ.get("FISH_LATENCY", "normal").strip() or "normal",
        "temperature": _unit_env("FISH_TEMPERATURE", "0.7"),
        "top_p": _unit_env("FISH_TOP_P", "0.7"),
        "model_api": os.environ.get("FISH_MODEL_API_URL", MODEL_API_URL).rstrip("/"),
        "http_attempts": 0,
    }


def _check_url(url: str, key: str) -> str:
    # Die Adresse nicht in die Meldung schreiben: sie kann den Schlüssel enthalten.
    encoded = urllib.parse.quote(key, safe="")
    if key in url or (encoded != key and encoded in url):
        raise RuntimeError("FISH_API_URL darf den Schlüssel nicht enthalten")
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise RuntimeError("FISH_API_URL muss http oder https sein")
    return url


def _masked_forms(key: str) -> tuple[str, ...]:
    forms = (
        urllib.parse.quote(key, safe=""),
        urllib.parse.quote(key, safe="/"),
        html.escape(key, quote=True),
    )
    return tuple(dict.fromkeys(form for form in forms if form != key))


def _clean(cfg: dict, text: str) -> str:
    key = cfg["key"]
    hidden = text.replace(key, "***")
    for form in _masked_forms(key):
        hidden = hidden.replace(form, "***")
    return hidden


def _error_detail(cfg: dict, err: urllib.error.HTTPError) -> str:
    # Erst begrenzen, dann maskieren, dann kürzen: ein Schlüssel über der Kürzungsgrenze bleibt sonst als Präfix stehen.
    raw = err.read(_MAX_ERROR_BODY)
    return _clean(cfg, raw.decode("utf-8", "replace"))[:200]


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
    request = urllib.request.Request(
        cfg["url"],
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {cfg['key']}",
            "Content-Type": "application/json",
            "model": cfg["model"],
        },
    )
    cfg["http_attempts"] = 0
    started = time.monotonic()
    last = "unbekannt"
    for attempt in range(cfg["attempts"]):
        remaining = cfg["deadline"] - (time.monotonic() - started)
        if remaining <= 0:
            break
        cfg["http_attempts"] = attempt + 1
        wait = cfg["backoff"] * (2**attempt)
        try:
            with _OPENER.open(request, timeout=min(REQUEST_TIMEOUT_S, remaining)) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                raise RuntimeError(f"Fish leitet um (HTTP {e.code}); nicht gefolgt") from None
            detail = _error_detail(cfg, e)
            if e.code not in _RETRY_STATUS:
                raise RuntimeError(f"Fish lehnt die Anfrage ab (HTTP {e.code}): {detail}") from None
            last, wait = f"HTTP {e.code}", _retry_after(e.headers, wait)
        except http.client.HTTPException as e:
            # Antwort bricht mitten im Body ab (IncompleteRead, BadStatusLine)
            last = type(e).__name__
        except OSError as e:  # Verbindungsfehler, Zeitüberschreitung
            last = type(e).__name__
        except Exception as e:  # noqa: BLE001 – z. B. ValueError/UnicodeEncodeError beim Header-Aufbau in http.client
            raise RuntimeError(f"Fish-Anfrage fehlgeschlagen: {_clean(cfg, str(e))}") from None
        remaining = cfg["deadline"] - (time.monotonic() - started)
        if attempt >= cfg["attempts"] - 1 or wait > remaining:
            break
        time.sleep(wait)
    raise RuntimeError(
        f"Fish nicht erreichbar nach {cfg['http_attempts']} Versuchen (zuletzt {last})"
    )


def _fix_streaming_wav(audio: bytes) -> bytes:
    """Fish streamt WAVs mit Platzhaltergrößen (RIFF- und data-Größe ~0xFFFFFFxx).

    Maßgeblich sind die tatsächlich vorhandenen Bytes: Header auf diese Größen setzen und ein
    angefangenes Frame abschneiden. Korrekte WAVs kommen unverändert zurück.
    """
    if len(audio) < 12 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return audio  # wave.open meldet das in synth()
    frame_size, data_at, declared = 0, None, 0
    pos = 12
    while pos + 8 <= len(audio) and (frame_size == 0 or data_at is None):
        cid = audio[pos : pos + 4]
        size = struct.unpack_from("<I", audio, pos + 4)[0]
        body = pos + 8
        if cid == b"fmt " and size >= 16 and body + 16 <= len(audio):
            _tag, channels, _rate, _byte_rate, _align, bits = struct.unpack_from(
                "<HHIIHH", audio, body
            )
            frame_size = channels * ((bits + 7) // 8)
        elif cid == b"data":
            data_at, declared = pos, size
        pos = body + size + (size & 1)  # Chunks sind auf gerade Länge gepolstert
    if frame_size == 0:
        raise ValueError("fmt-Chunk fehlt oder ist unbrauchbar")
    if data_at is None:
        raise ValueError("kein data-Chunk")
    start = data_at + 8
    usable = min(declared, len(audio) - start)
    usable -= usable % frame_size
    if usable <= 0:
        raise ValueError("data-Chunk ohne Audio")
    if usable == declared and struct.unpack_from("<I", audio, 4)[0] == len(audio) - 8:
        return audio
    fixed = bytearray(audio[: start + usable])
    struct.pack_into("<I", fixed, 4, len(fixed) - 8)
    struct.pack_into("<I", fixed, data_at + 4, usable)
    return bytes(fixed)


def _classify_model(payload: dict) -> str:
    if payload.get("dmca_taken_down") is True:
        return "taken_down"
    if payload.get("state") == "failed":
        return "unavailable"
    if payload.get("pvc_release_state") == "retiring":
        return "retiring"
    return "ok"


def lookup_model(cfg: dict, model_id: str) -> dict:
    """GET /model/{id}. 404 heißt, die Stimme ist weg. Der Schlüssel steht in keiner Meldung."""
    url = f"{cfg['model_api']}/{model_id}"
    request = urllib.request.Request(
        url, method="GET", headers={"Authorization": f"Bearer {cfg['key']}"}
    )
    try:
        with _OPENER.open(request, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            raise RuntimeError(f"Fish leitet um (HTTP {e.code}); nicht gefolgt") from None
        detail = _clean(cfg, e.read().decode("utf-8", "replace"))[:200]
        if e.code == 404:
            return {"id": model_id, "status": "missing"}
        if e.code in (401, 403):
            raise RuntimeError(f"Fish lehnt die Anfrage ab (HTTP {e.code}): {detail}") from None
        return {"id": model_id, "status": "error", "detail": f"HTTP {e.code}: {detail}"}
    except OSError as e:
        return {"id": model_id, "status": "error", "detail": type(e).__name__}
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return {"id": model_id, "status": "error", "detail": "Antwort ist kein JSON"}
    if not isinstance(payload, dict):
        return {"id": model_id, "status": "error", "detail": "Antwort ist kein Objekt"}
    found = {"id": model_id, "status": _classify_model(payload)}
    retire_at = payload.get("pvc_retire_effective_at")
    if isinstance(retire_at, str) and retire_at:
        found["retire_at"] = retire_at
    return found


def check_voices(cfg: dict, ids: list) -> dict:
    return {"voices": [lookup_model(cfg, model_id) for model_id in ids]}


def _check_main() -> None:
    cfg = None
    try:
        cfg = load()
        req = json.loads(sys.stdin.read() or "{}")
        ids = req.get("ids") if isinstance(req, dict) else None
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise RuntimeError("ids muss eine Liste von Texten sein")
        json.dump(check_voices(cfg, ids), sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    except Exception as e:  # noqa: BLE001 – Grund an den Aufrufer, Schlüssel bleibt draußen
        message = f"{type(e).__name__}: {e}"
        if cfg is not None:
            message = _clean(cfg, message)
        print(message, file=sys.stderr)
        sys.exit(1)


def _text_param(params: dict, key: str, fallback: str) -> str:
    value = params.get(key)
    if value is None or value == "":
        return fallback
    return str(value)


def _sampling_number(params: dict, key: str, fallback: float) -> float:
    if key not in params or params[key] is None or params[key] == "":
        return fallback
    try:
        number = float(params[key])
    except (TypeError, ValueError):
        raise ValueError(f"{key} ist keine Zahl") from None
    if not math.isfinite(number) or not 0 < number <= 1:
        raise ValueError(f"{key} muss größer als 0 und höchstens 1 sein")
    return number


def synth(cfg: dict, req: dict) -> tuple[int, float]:
    cfg["http_attempts"] = 0
    if req.get("reference"):
        raise ValueError(
            "Fish nutzt eine Stimmen-ID (voice = reference_id), keine lokale Referenz-WAV"
        )
    raw_params = req.get("params")
    params: dict = raw_params if isinstance(raw_params, dict) else {}
    language = _text_param(params, "language", cfg["language"])
    latency = _text_param(params, "latency", cfg["latency"])
    if not _LANG.fullmatch(language):
        raise ValueError("language muss ein BCP-47-Kürzel sein, z. B. de")
    if latency not in _LATENCIES:
        raise ValueError("latency muss normal, balanced oder low sein")
    body = {
        "text": req["text"],
        "format": "wav",
        "language": language,
        "latency": latency,
        "temperature": _sampling_number(params, "temperature", cfg["temperature"]),
        "top_p": _sampling_number(params, "top_p", cfg["top_p"]),
    }
    if req.get("voice"):
        body["reference_id"] = req["voice"]
    audio = _post(cfg, body)
    out = Path(req["out_path"])
    try:
        out.write_bytes(_fix_streaming_wav(audio))
        with wave.open(str(out), "rb") as w:
            rate, frames = w.getframerate(), w.getnframes()
    except (wave.Error, EOFError, ValueError) as e:
        out.unlink(missing_ok=True)
        raise RuntimeError(f"Fish lieferte kein gültiges WAV: {e}") from None
    return rate, frames / rate


if __name__ == "__main__":
    if os.environ.get("FISH_VOICE_CHECK") == "1":
        _check_main()
    else:
        serve("fish", f"fish-audio/{MODEL}", load, synth)
