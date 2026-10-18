from __future__ import annotations

import contextlib
import hashlib
import json
import queue
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, ContextManager, Mapping, Sequence

from drova_voice.casting import Casting
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineError
from drova_voice.engines.protocol import SynthRequest
from drova_voice.fish_voices import FishVoice
from drova_voice.jsonl import replace_with_retry
from drova_voice.lines import SKIP_UNSPEAKABLE, Line, emotion_id
from drova_voice.render import render_request

SKIP_NO_VOICE = "no_voice"

# Fish, Deutsch, gemessen 2026-10-12 (docs/decisions/2026-10-fish-throughput.md): 37.068 Zeichen -> 2.169 s Audio.
CHARS_PER_SECOND = 17.0
MIN_RATIO, MAX_RATIO = 0.4, 2.5  # Dauer / erwartete Dauer
MIN_SECONDS = 0.25
SHORT_EXPECTED_SECONDS = 1.0  # darunter gilt nur die Obergrenze
SHORT_MAX_SECONDS = 5.0
MAX_ATTEMPTS = 3
ABORT_AFTER = 5  # so viele Aufträge in Folge mit Guthaben-/Limit-/Anmeldefehler stoppen den Lauf
_FATAL = (("HTTP 402", "Guthaben aufgebraucht"), ("HTTP 401", "Anmeldung abgelehnt (API-Schlüssel prüfen)"),
          ("HTTP 403", "Zugriff verweigert"), ("HTTP 429", "Ratenlimit erreicht"),
          ("nicht erreichbar", "Dienst nicht erreichbar"))


@dataclass(frozen=True)
class SynthJob:
    id: str
    text: str  # bereits für die Engine gerendert (Emotions-Cues)
    speech_len: int  # Länge des Sprechtexts ohne Cues, für die Plausibilität
    voice: str | None
    params: dict


@dataclass(frozen=True)
class SynthResult:
    id: str
    key: str
    wav: str | None
    duration: float | None
    ok: bool
    attempts: int
    flagged: bool  # Dauer unplausibel, trotzdem behalten (Bericht)
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def fatal_reason(error: str | None) -> str | None:
    """Grund, wenn der Fehler nach Guthaben, Limit oder Anmeldung aussieht (dann hilft Weitermachen nicht)."""
    for needle, reason in _FATAL:
        if needle in (error or ""):
            return reason
    return None


@dataclass
class SynthStatus:
    aborted: str | None = None  # Grund des Abbruchs
    not_run: int = 0  # Aufträge, die wegen des Abbruchs nicht gestartet wurden
    sent_requests: int = 0  # abgesetzte Anfragen, jeder Versuch einzeln
    sent_chars: int = 0  # Zeichen des jeweils gesendeten Texts
    sent_bytes: int = 0  # UTF-8-Bytes davon (Fish rechnet so ab; Umlaute zählen doppelt)


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def make_key(engine: str, model: str | None, voice: str | None, text: str, params: Mapping) -> str:
    payload = json.dumps([engine, model, voice, text, dict(params)], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def plausible(duration: float | None, speech_len: int) -> bool:
    if duration is None or duration < MIN_SECONDS:
        return False
    expected = speech_len / CHARS_PER_SECOND
    if expected < SHORT_EXPECTED_SECONDS:
        return duration <= SHORT_MAX_SECONDS
    return MIN_RATIO <= duration / expected <= MAX_RATIO


def build_jobs(lines: Sequence[Line], casting: Casting, fish_table: Mapping[str, FishVoice],
               emotions: Mapping[str, EmotionTag], engine: str) -> tuple[list[SynthJob], dict[str, str]]:
    jobs: list[SynthJob] = []
    skipped: dict[str, str] = {}
    for line in lines:
        if line.skip:
            skipped[line.id] = line.skip
            continue
        voice_key = casting.voice_for(line)
        if voice_key is None:
            skipped[line.id] = SKIP_NO_VOICE
            continue
        voice = fish_table[voice_key].id if engine == "fish" else None
        try:
            text, params = render_request(engine, line.speech, emotions.get(emotion_id(line), EmotionTag()))
        except ValueError:
            skipped[line.id] = SKIP_UNSPEAKABLE
            continue
        jobs.append(SynthJob(line.id, text, len(line.speech), voice, params))
    return jobs, skipped


def cache_hit(job: SynthJob, key: str, cache_dir: Path) -> SynthResult | None:
    """Fertige WAV im Cache (nur fertige Dateien liegen unter dem endgültigen Namen); kaputte Dateien werden verworfen."""
    wav = Path(cache_dir) / f"{key}.wav"
    if not wav.exists():
        return None
    try:
        duration = wav_duration(wav)
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        wav.unlink(missing_ok=True)
        return None
    return SynthResult(job.id, key, str(wav), duration, True, 0, not plausible(duration, job.speech_len), None)


def synth_one(client, job: SynthJob, key: str, cache_dir: Path, max_attempts: int = MAX_ATTEMPTS,
              on_sent: Callable[[str], None] | None = None) -> SynthResult:
    hit = cache_hit(job, key, cache_dir)
    if hit is not None:
        return hit
    wav = Path(cache_dir) / f"{key}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    part = wav.with_name(f"{key}.part.wav")
    duration: float | None = None  # Dauer der Datei, die gerade unter dem endgültigen Namen liegt
    error: str | None = None
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        # Vor dem Aufruf: auch ein Fehlversuch und jede Wiederholung ist eine gesendete Anfrage.
        # Wirft der Client, bleibt die Zählung stehen (der Text wurde bereits übergeben).
        if on_sent is not None:
            on_sent(job.text)
        resp = client.synth(SynthRequest(id=job.id, text=job.text, out_path=str(part), voice=job.voice, params=job.params))
        if not resp.ok:
            error = resp.error or "unbekannter Fehler"
            part.unlink(missing_ok=True)
            continue
        replace_with_retry(part, wav)  # brauchbaren Ton sofort sichern, auch wenn ein späterer Versuch scheitert
        duration, error = resp.duration, None
        if plausible(duration, job.speech_len):
            break
    if duration is None:
        return SynthResult(job.id, key, None, None, False, attempt, False, error)
    return SynthResult(job.id, key, str(wav), duration, True, attempt, not plausible(duration, job.speech_len), None)


def _acquire(idle: "queue.Queue", alive: list[int], lock: threading.Lock):
    while True:
        try:
            return idle.get(timeout=0.2)
        except queue.Empty:
            with lock:
                if alive[0] == 0:
                    return None


def run_synth(jobs: Sequence[SynthJob], engine: str, client_factory: Callable[[str], ContextManager],
              cache_dir: Path, workers: int = 8,
              on_result: Callable[[SynthResult], None] | None = None,
              status: SynthStatus | None = None) -> list[SynthResult]:
    jobs = list(jobs)
    if not jobs:
        return []
    results: list[SynthResult] = []
    lock = threading.Lock()
    with contextlib.ExitStack() as stack:
        clients = [stack.enter_context(client_factory(engine)) for _ in range(max(1, min(workers, len(jobs))))]
        model = getattr(clients[0], "model", None)
        keys = {j.id: make_key(engine, model, j.voice, j.text, j.params) for j in jobs}
        first_by_key: dict[str, SynthJob] = {}
        followers: dict[str, list[SynthJob]] = {}
        for j in jobs:  # gleicher Text + Stimme + Parameter: nur einmal erzeugen
            if keys[j.id] in first_by_key:
                followers.setdefault(keys[j.id], []).append(j)
            else:
                first_by_key[keys[j.id]] = j
        idle: "queue.Queue" = queue.Queue()
        for c in clients:
            idle.put(c)
        alive = [len(clients)]
        stop = threading.Event()
        streak = [0]
        why: list[str | None] = [None]
        not_run = [0]

        def emit(r: SynthResult) -> None:
            with lock:
                results.append(r)
                if on_result is not None:
                    on_result(r)

        def note(r: SynthResult) -> None:  # nur echte Anfragen zählen, Cache-Treffer nicht
            with lock:
                reason = None if r.ok else fatal_reason(r.error)
                if reason is None:
                    streak[0] = 0
                    return
                streak[0] += 1
                if streak[0] >= ABORT_AFTER and not stop.is_set():
                    stop.set()
                    why[0] = reason

        def on_sent(text: str) -> None:
            chars, utf8_bytes = len(text), len(text.encode("utf-8"))
            with lock:
                status.sent_requests += 1
                status.sent_chars += chars
                status.sent_bytes += utf8_bytes

        def work(job: SynthJob) -> None:
            key = keys[job.id]
            r = cache_hit(job, key, cache_dir)  # Cache-Treffer brauchen keinen Worker (auch nicht, wenn alle tot sind)
            if r is None:
                if stop.is_set():  # abgebrochen: nichts mehr starten, auch keine Fehlerzeile schreiben
                    with lock:
                        not_run[0] += 1 + len(followers.get(key, []))
                    return
                client = _acquire(idle, alive, lock)
                if client is None:
                    r = SynthResult(job.id, key, None, None, False, 0, False, "kein Worker mehr verfügbar")
                else:
                    try:
                        r = synth_one(client, job, key, cache_dir, on_sent=on_sent if status is not None else None)
                    except EngineError as e:  # Worker tot: nicht zurücklegen, Rest dieses Laufs scheitert sauber
                        with lock:
                            alive[0] -= 1
                        r = SynthResult(job.id, key, None, None, False, 0, False, str(e))
                    except Exception as e:  # z. B. gesperrte Cache-Datei: Worker ist in Ordnung, dieser Auftrag nicht
                        idle.put(client)
                        r = SynthResult(job.id, key, None, None, False, 0, False, f"{type(e).__name__}: {e}")
                    else:
                        idle.put(client)
                    if not r.ok:
                        (Path(cache_dir) / f"{key}.part.wav").unlink(missing_ok=True)
                note(r)
            emit(r)
            for other in followers.get(key, []):
                emit(SynthResult(other.id, key, r.wav, r.duration, r.ok, r.attempts, r.flagged, r.error))

        with ThreadPoolExecutor(max_workers=len(clients)) as pool:
            list(pool.map(work, first_by_key.values()))
        if status is not None:
            status.aborted, status.not_run = why[0], not_run[0]
    return results
