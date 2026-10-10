# DrovaVoice Plan 2: Fish-Engine und Export (M1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Cloud-Engine Fish Audio als Engine-Worker anbinden und messen (Teil A), und den Dialog-Export des Spiels bauen, der `manifest.json` samt Abdeckungsbericht liefert (Teil B, Meilenstein M1).

**Architecture:** Teil A erweitert die Python-Pipeline aus Plan 1 um einen Worker `fish` (nur Standardbibliothek, JSON-Lines-Protokoll wie die anderen Worker, HTTP statt lokalem Modell) und eine Emotions-Übersetzung `render_fish`. Teil B legt reine Logik (Kategorien, GVAR-Erkennung, Manifest-Format, Katalog-Leser) in `DrovaVoice.Core` ab (xUnit-getestet) und den Il2Cpp-abhängigen Export in die Mod `DrovaVoice` (im Spiel geprüft, gegen die echten Assemblies kompiliert). Python prüft das Ergebnis mit `drova-voice export report` gegen die `.loc`-Dateien.

**Tech Stack:** Python 3.12 (pytest, nur stdlib im Fish-Worker), C# net6.0 (Core, Mod), xUnit (net8.0 Testprojekt), MelonLoader 0.7.3, Drova Modding API 0.5.4, Harmony nicht nötig.

**Spec:** `docs/superpowers/specs/2026-10-10-drova-voice-design.md` (§5 Export, §6 Generator, §10 M1, §15 Änderungen nach dem Hörtest). Entscheidung: `docs/decisions/2026-10-tts-engine.md`. Der Vorgänger-Plan `docs/superpowers/plans/2026-10-10-plan-1-fundament-hoertest.md` ist fertig (Branch `plan-1-foundation`); Plan 2 baut darauf auf. Der Durchstich mit einem NPC (M3) und die Wiedergabe sind **Plan 3**, nach den Ergebnissen aus Teil B.

## Global Constraints

- Das Repo enthält **keine Spieltexte und kein Audio** (Spec §1). Tests und Fixtures verwenden erfundenen Text und erfundene Bezeichner (`DT_Main_NPC_Test`, `QuestVars_Beispiel_Config.Betrag`).
- Zeilen-ID: Aussage `{treeName}|{locaPath}|{locaKey}`, Auswahloption `{treeName}|{locaPath}|{locaKey}|c{choiceIndex}`; `locaPath` ist `GlobalLocaPath`, wenn `useGlobalLoca` gesetzt ist, sonst `LocaPath` des Baums, mit `/` normalisiert (Spec §4). IDs bildet nur `LineIds` (C#) bzw. `drova_voice.ids` (Python).
- Kategorie: Spieler -> `player`; SVM-/Welt-Bäume (`DT_World*`, `DT_Generic_Combat_*`, `DT_Comment_*`, `*_WorldDialogue(s)`) -> `bark`; alles andere `dialog`. Generische Sprecher (`NPC`, `TEACHER`, `INSTIGATOR`, `DRUID`, `Participant`, `ACTOR`) bekommen das Flag `generic` (Spec §5).
- Abdeckung: >= 98 % der Einträge in `Dialog*/`, `Dialogues/` und `*World*.loc` stehen im Manifest; der Bericht listet die fehlenden auf (Spec §5).
- C#: `DrovaVoice.Core` ist `net6.0` ohne Il2Cpp-Abhängigkeit; das Testprojekt ist `net8.0` (vorhanden). Der Mod-Spielpfad kommt aus `Directory.Build.props` / `DROVA_GAME_DIR`.
- Der Fish-Schlüssel liegt **nur** in der Umgebungsvariable `FISH_API_KEY`. Er darf in keiner Datei, keinem Log, keiner Fehlermeldung und keinem Commit stehen.
- Fish-Cues sind englisch und stehen in eckigen Klammern; Kitten bekommt keine Laut-Tags (Spec §15). Fehlermeldungen für den Nutzer sind deutsch.
- Downloads, Installationen und Daten, die den Rechner verlassen (Fish-Aufrufe mit Spieltext), werden vor der Ausführung einzeln mit dem Nutzer abgestimmt (Spec §13). Änderungen im Spielordner entstehen nur durch den Mod-Build (`Mods/`, `UserLibs/`) und den Exportordner `Mods/DrovaVoice/Export/`.
- Jeder Commit endet mit `Co-Authored-By: <Modell> <noreply@anthropic.com>`; die Ausgabe von `git log` enthält keine echten Spieltexte.

## Review Focus

- Fish antwortet mit 429/5xx/Netzfehler mitten im Lauf: der Worker wiederholt mit Wartezeit, meldet nach dem Limit einen deutschen Fehler und lebt weiter; 401/402 werden **nicht** wiederholt; der Schlüssel taucht nie in einer Fehlermeldung auf (Task 2).
- Ein Text, der nach dem Rendern keine Buchstaben enthält, oder ein Cue ohne Text erzeugt Stille oder Müll bei Fish (Task 1: `render_request` lehnt ihn ab; Task 2: Antwort ohne Audio ist ein Fehler).
- Ein Baum lässt sich nicht deserialisieren, hat Knoten ohne Verbindungen, doppelte Schlüssel oder `[LOCA] Key not found`: der Export überspringt die Zeile, zählt sie und bricht nicht ab (Task 8).
- Export wird zweimal ausgelöst oder während eines Gesprächs: der zweite Auslöser wird ignoriert, es entsteht nie eine halb geschriebene `manifest.json` (Task 8).
- Manifest und `.loc` unterscheiden sich in Schreibung (`\` statt `/`, `_de`-Suffix, BOM, Groß-/Kleinschreibung der Dateinamen): die Abdeckung vergleicht normalisierte Pfade und zählt jede Abweichung als fehlend statt sie zu verschlucken (Task 7).

---

## Datei-Übersicht

**Python (`generator/`)**
- `drova_voice/render.py` (ändern): `render_fish`, `fish`-Zweig in `render_request`
- `workers/fish/worker.py` (neu): Fish-Worker, nur stdlib
- `drova_voice/fish_voices.py` (neu): Tabelle der offiziellen Stimmen, Auflösung Name -> ID
- `drova_voice/bakeoff.py` (ändern): `VoiceSpec.label`, Auflösung der Fish-Stimmennamen in `load_voice_specs`
- `drova_voice/export_report.py` (neu): Abdeckung Manifest gegen `.loc`
- `drova_voice/cli.py` (ändern): `export report`, `export fetch`
- `tests/test_render.py`, `tests/test_fish_worker.py`, `tests/test_fish_voices.py`, `tests/test_export_report.py` (ändern/neu)

**Repo-Wurzel**
- `casting/fish_voices.yaml` (neu): nur IDs und Labels der offiziellen Stimmen
- `docs/decisions/2026-10-fish-throughput.md` (neu, Task 4), `docs/export.md` (neu, Task 11)

**C# (`mod/`)**
- `DrovaVoice.Core/LineClassifier.cs`, `Manifest.cs`, `CatalogReader.cs` (neu)
- `DrovaVoice.Core.Tests/LineClassifierTests.cs`, `ManifestTests.cs`, `CatalogReaderTests.cs` (neu)
- `DrovaVoice/DrovaVoice.csproj` (ändern: Il2Cpp-Referenzen)
- `DrovaVoice/DrovaVoiceMod.cs` (ändern: Auslöser)
- `DrovaVoice/Export/DialogueExporter.cs`, `TreeSource.cs`, `ManifestFile.cs`, `NpcExporter.cs` (neu)

---

# Teil A: Fish-Engine

### Task 1: Emotions-Übersetzung für Fish (`render_fish`)

**Files:**
- Modify: `generator/drova_voice/render.py`
- Test: `generator/tests/test_render.py`

**Interfaces:**
- Consumes: `EmotionTag(emotion, intensity, events, emphasis, notes, source)`, `Event(tag, pos)` aus `drova_voice.emotions`.
- Produces: `render_fish(text: str, tag: EmotionTag) -> str`; `render_request("fish", text, tag) -> (str, {})`.

- [ ] **Step 1: Failing Tests schreiben**

An `generator/tests/test_render.py` anhängen (Imports oben um `render_fish` ergänzen: `from drova_voice.render import chatterbox_params, render_fish, render_kitten, render_request`):

```python
def test_fish_neutral_text_is_plain():
    assert render_fish("Hallo,   Welt.", EmotionTag()) == "Hallo, Welt."


@pytest.mark.parametrize("emotion, intensity, expected", [
    ("angry", 0.5, "[angry] Raus!"),
    ("angry", 0.9, "[very angry] Raus!"),
    ("joyful", 0.5, "[happy] Raus!"),
    ("contemplative", 0.5, "[thoughtful] Raus!"),
    ("sad", 0.3, "[sad] Raus!"),
    ("sad", 0.29, "Raus!"),
    ("mundane", 0.9, "Raus!"),
    ("neutral", 0.9, "Raus!"),
])
def test_fish_emotion_prefix(emotion, intensity, expected):
    assert render_fish("Raus!", EmotionTag(emotion, intensity)) == expected


def test_fish_events_are_inserted_at_their_position_and_unknown_ones_dropped():
    tag = EmotionTag(events=[Event("sigh", 6), Event("gasp", 0), Event("um", 3)])
    assert render_fish("Hallo! Du hier?", tag) == "Hallo! [sighing] Du hier?"
    assert render_fish("Na gut.", EmotionTag(events=[Event("pause", 0), Event("laugh", 99)])) == "[break] Na gut. [laughing]"


def test_fish_emphasis_marks_the_first_whole_word_but_never_inside_a_cue():
    tag = EmotionTag(emphasis=["nie"])
    assert render_fish("Das mache ich nie wieder, nie.", tag) == "Das mache ich [emphasis] nie wieder, nie."
    assert render_fish("Niemand.", tag) == "Niemand."
    tag = EmotionTag(events=[Event("pause", 0)], emphasis=["break"])
    assert render_fish("Ein break hier", tag) == "[break] Ein [emphasis] break hier"


def test_render_request_for_fish_has_no_params_and_rejects_unspeakable_text():
    tag = EmotionTag("angry", 1.0, [Event("sigh", 0)])
    assert render_request("fish", "Raus!", tag) == ("[very angry] [sighing] Raus!", {})
    with pytest.raises(ValueError, match="nicht sprechbar"):
        render_request("fish", "... *", EmotionTag())
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_render.py -q`
Expected: FAIL mit `ImportError: cannot import name 'render_fish'`.

- [ ] **Step 3: Implementieren**

In `generator/drova_voice/render.py` nach den Konstanten ergänzen:

```python
FISH_MIN_INTENSITY = 0.3
FISH_STRONG_INTENSITY = 0.8
# Emotionsname im Projekt -> Fish-Cue (englisch, frei formulierbar; nur Cues, die im Hörtest verwendet wurden).
_FISH_CUES = {
    "angry": "angry", "sad": "sad", "joyful": "happy", "stern": "stern", "excited": "excited",
    "nervous": "nervous", "tender": "tender", "surprised": "surprised", "contemplative": "thoughtful",
}
# Laute, deren Wirkung geprüft ist; andere Ereignisse werden weggelassen.
_FISH_EVENTS = {"sigh": "[sighing]", "laugh": "[laughing]", "pause": "[break]"}


def render_fish(text: str, tag: EmotionTag) -> str:
    s = text
    n = len(text)
    placed = sorted(
        ((max(0, min(ev.pos, n)), i, ev) for i, ev in enumerate(tag.events) if ev.tag in _FISH_EVENTS), reverse=True
    )
    for p, _, ev in placed:
        s = f"{s[:p]} {_FISH_EVENTS[ev.tag]} {s[p:]}"
    s = re.sub(r"\s+", " ", s).strip()
    for word in tag.emphasis:
        s = re.sub(rf"(?<![\w\[\]])({re.escape(word)})(?![\w\[\]])", r"[emphasis] \1", s, count=1)
    cue = _FISH_CUES.get(tag.emotion)
    if cue and tag.intensity >= FISH_MIN_INTENSITY:
        s = f"[{'very ' + cue if tag.intensity >= FISH_STRONG_INTENSITY else cue}] {s}"
    return s
```

In `render_request` vor `raise ValueError(f"Unbekannte Engine: {engine}")` ergänzen:

```python
    if engine == "fish":
        return render_fish(text, tag), {}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest -q`
Expected: alle Tests grün (vorher 239, jetzt plus die neuen).

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/render.py generator/tests/test_render.py
git commit -m "Add the Fish cue renderer" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Fish-Worker (HTTP, nur stdlib)

**Files:**
- Create: `generator/workers/fish/worker.py`
- Test: `generator/tests/test_fish_worker.py`

**Interfaces:**
- Consumes: `serve(engine, model, load, synth, warmup_text=None)` aus `workers/_common/worker_loop.py`; `EngineClient(cmd, cwd=None, env=None)`, `worker_command(workers_dir, engine)`, `SynthRequest(id, text, out_path, voice, reference, params)` (alle aus Plan 1); Fixture `guarded` aus `tests/conftest.py`.
- Produces: Worker `fish`. Umgebungsvariablen: `FISH_API_KEY` (Pflicht), `FISH_API_URL` (Standard `https://api.fish.audio/v1/tts`), `FISH_MODEL` (Standard `s2.1-pro-free`), `FISH_MAX_ATTEMPTS` (Standard 5), `FISH_BACKOFF_S` (Standard 2.0). `SynthRequest.voice` ist die Fish-Modell-ID (`reference_id`); `reference` wird abgelehnt. In `workers/fish/` liegt **keine** `requirements.txt` (sonst verlangt `worker_command` ein venv).

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_fish_worker.py`:

```python
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from drova_voice.engines.client import EngineClient, EngineError, worker_command
from drova_voice.engines.protocol import SynthRequest

WORKERS = Path(__file__).resolve().parents[1] / "workers"
KEY = "sk-test-geheim-123"


def _wav_bytes(seconds: float = 0.5, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class FakeFish:
    """Lokaler Server: spielt eine Liste von Antworten ab und merkt sich die Anfragen."""

    def __init__(self, responses):
        self.responses = list(responses)  # Einträge: (status, body_bytes) oder (status, body, {"Retry-After": "0"})
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                status, payload, *extra = outer.responses.pop(0) if outer.responses else (503, b"leer")
                self.send_response(status)
                for k, v in (extra[0] if extra else {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1/tts"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def _client(guarded, fake, **env):
    base = {"FISH_API_KEY": KEY, "FISH_API_URL": fake.url, "FISH_BACKOFF_S": "0.01", "FISH_MAX_ATTEMPTS": "3"}
    base.update(env)
    return guarded(lambda: EngineClient(worker_command(WORKERS, "fish"), env=base))


def _req(tmp_path, text="[sad] Hallo.", voice="abc123", **kw):
    return SynthRequest(id="t1", text=text, out_path=str(tmp_path / "a.wav"), voice=voice, **kw)


def test_success_writes_wav_and_sends_voice_text_and_headers(tmp_path, guarded):
    with FakeFish([(200, _wav_bytes(0.5))]) as fake:
        client = _client(guarded, fake, FISH_MODEL="s2.1-pro-free")
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert resp.ok and resp.sample_rate == 22050 and resp.duration == pytest.approx(0.5, abs=0.01)
    assert (tmp_path / "a.wav").stat().st_size > 44
    sent = fake.requests[0]
    # urllib schreibt Header-Namen groß ("Model"); HTTP-Header sind ohnehin nicht groß-/kleinschreibungsabhängig.
    assert sent["headers"]["authorization"] == f"Bearer {KEY}" and sent["headers"]["model"] == "s2.1-pro-free"
    assert sent["body"]["text"] == "[sad] Hallo." and sent["body"]["reference_id"] == "abc123" and sent["body"]["format"] == "wav"


def test_busy_server_is_retried_with_backoff_until_it_succeeds(tmp_path, guarded):
    with FakeFish([(429, b"zu viele", {"Retry-After": "0"}), (503, b"busy"), (200, _wav_bytes())]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert resp.ok and len(fake.requests) == 3


def test_gives_up_after_the_attempt_limit_with_a_german_error(tmp_path, guarded):
    with FakeFish([(503, b"busy")] * 5) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "nicht erreichbar" in resp.error and "503" in resp.error
    assert len(fake.requests) == 3
    assert not (tmp_path / "a.wav").exists()


@pytest.mark.parametrize("status", [401, 402, 400])
def test_client_errors_are_not_retried_and_never_leak_the_key(tmp_path, guarded, status):
    with FakeFish([(status, f"abgelehnt mit {KEY}".encode())] * 3) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and str(status) in resp.error
    assert KEY not in resp.error and len(fake.requests) == 1


def test_missing_key_reports_the_reason_at_startup(tmp_path, guarded):
    with FakeFish([]) as fake:
        with pytest.raises(EngineError, match="FISH_API_KEY"):
            _client(guarded, fake, FISH_API_KEY="")


def test_local_reference_wav_is_rejected_because_fish_uses_voice_ids(tmp_path, guarded):
    with FakeFish([(200, _wav_bytes())]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path, reference="ref.wav")))
        finally:
            client.close()
    assert not resp.ok and "reference_id" in resp.error and not fake.requests


def test_broken_audio_answer_is_an_error_not_a_success(tmp_path, guarded):
    with FakeFish([(200, b"das ist kein wav")]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_fish_worker.py -q`
Expected: FAIL (`Unbekannte Engine 'fish': …worker.py fehlt`).

- [ ] **Step 3: Worker schreiben**

`generator/workers/fish/worker.py`:

```python
"""Fish-Audio-Worker: ruft die Cloud-API auf. Nur Standardbibliothek, kein venv nötig."""
from __future__ import annotations

import json
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


def load() -> dict:
    key = os.environ.get("FISH_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FISH_API_KEY fehlt: den Schlüssel nur als Umgebungsvariable setzen (nie in Dateien oder ins Repo)")
    return {
        "key": key,
        "url": os.environ.get("FISH_API_URL", API_URL),
        "model": os.environ.get("FISH_MODEL", MODEL),
        "attempts": int(os.environ.get("FISH_MAX_ATTEMPTS", "5")),
        "backoff": float(os.environ.get("FISH_BACKOFF_S", "2.0")),
    }


def _clean(cfg: dict, text: str) -> str:
    return text.replace(cfg["key"], "***")


def _retry_after(headers, default: float) -> float:
    try:
        return min(60.0, float(headers.get("Retry-After")))
    except (TypeError, ValueError):
        return default


def _post(cfg: dict, body: dict) -> bytes:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(cfg["url"], data=data, method="POST", headers={
        "Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json", "model": cfg["model"]})
    last = "unbekannt"
    for attempt in range(cfg["attempts"]):
        wait = cfg["backoff"] * (2 ** attempt)
        try:
            with urllib.request.urlopen(request, timeout=180) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            detail = _clean(cfg, e.read()[:200].decode("utf-8", "replace"))
            if e.code not in _RETRY_STATUS:
                raise RuntimeError(f"Fish lehnt die Anfrage ab (HTTP {e.code}): {detail}") from None
            last, wait = f"HTTP {e.code}", _retry_after(e.headers, wait)
        except OSError as e:  # Verbindungsfehler, Zeitüberschreitung
            last = type(e).__name__
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
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_fish_worker.py -q` und danach `.venv/Scripts/python -m pytest -q`
Expected: alle grün. Ein Test, der hängt, wird vom Fixture `guarded` nach 20 s beendet.

- [ ] **Step 5: Commit**

```bash
git add generator/workers/fish generator/tests/test_fish_worker.py
git commit -m "Add the Fish Audio worker" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Stimmentabelle der offiziellen Fish-Stimmen

**Files:**
- Create: `casting/fish_voices.yaml`, `generator/drova_voice/fish_voices.py`
- Modify: `generator/drova_voice/bakeoff.py` (`VoiceSpec.label`, `load_voice_specs`)
- Test: `generator/tests/test_fish_voices.py`

**Interfaces:**
- Consumes: `VoiceSpec(engine, voice=None, reference=None)` und `load_voice_specs(path, repo_root)` aus `drova_voice.bakeoff`.
- Produces: `FishVoice(key, id, label, gender, region)`; `load_fish_voices(path: Path) -> dict[str, FishVoice]`; `resolve_fish_voice(table, name_or_id: str) -> FishVoice` (Name ohne Beachtung der Groß-/Kleinschreibung, 32-stellige Hex-ID wird durchgereicht, sonst `ValueError` auf Deutsch); `VoiceSpec.label: str | None`; `VoiceSpec.slug` nutzt `label` zuerst.

- [ ] **Step 1: `casting/fish_voices.yaml` anlegen** (nur IDs und Labels; öffentliche IDs, keine Geheimnisse)

```yaml
# Offizielle deutsche Fish-Stimmen (Autor "Fish Official"). Nur IDs und Labels, kein Audio.
voices:
  lena:      {id: "3937b44b604249f18b94913daef94043", label: "Lena",                    gender: f, region: de}
  leon:      {id: "7b7c88bf825a4ab3bca27d55c26ddf16", label: "Leon",                    gender: m, region: de}
  melanie:   {id: "d979e92f9c8a489fa581f55f6b9e48da", label: "Melanie",                 gender: f, region: de}
  lukas:     {id: "c1e7cc926aa5469aa966c353094d4b0b", label: "Lukas (Österreich)",      gender: m, region: at}
  emma:      {id: "3235abc9a84b407d92f73539a5651720", label: "Emma",                    gender: f, region: de}
  elin:      {id: "0b96bf70a20d47f6b9e825d9cfe0e8c8", label: "Elin (Schweiz)",          gender: f, region: ch}
  jonas:     {id: "44f1ec96a51e429f8b87776cbc55a997", label: "Jonas",                   gender: m, region: de}
  valentina: {id: "e5fb46af69e0481fa0d2d0f209b07ae2", label: "Valentina (Österreich)",  gender: f, region: at}
```

Vor dem Commit prüfen: `python -c "import yaml,re;d=yaml.safe_load(open('casting/fish_voices.yaml',encoding='utf-8'));print(len(d['voices']),all(re.fullmatch('[0-9a-f]{32}',v['id']) for v in d['voices'].values()))"` -> `8 True`. Die Zuordnung Name -> ID stammt aus der API-Abfrage vom 2026-10-10 (Autor "Fish Official", Sprache de); bei Zweifel mit `GET https://api.fish.audio/model?title=<Name>&language=de` gegenprüfen.

- [ ] **Step 2: Failing Tests schreiben** (`generator/tests/test_fish_voices.py`)

```python
from pathlib import Path

import pytest

from drova_voice.bakeoff import VoiceSpec, load_voice_specs
from drova_voice.fish_voices import FishVoice, load_fish_voices, resolve_fish_voice

REAL_TABLE = Path(__file__).resolve().parents[2] / "casting" / "fish_voices.yaml"
ID_A = "a" * 32
ID_B = "b" * 32


def _table(tmp_path, body):
    p = tmp_path / "fish_voices.yaml"
    p.write_text(body, encoding="utf-8")
    return load_fish_voices(p)


def test_real_table_has_the_eight_official_voices_with_valid_ids():
    table = load_fish_voices(REAL_TABLE)
    assert len(table) == 8 and {"lena", "leon", "valentina"} <= set(table)
    assert all(len(v.id) == 32 and v.gender in ("m", "f") for v in table.values())


def test_resolve_by_name_ignores_case_and_passes_ids_through(tmp_path):
    table = _table(tmp_path, f"voices:\n  lena: {{id: '{ID_A}', label: Lena, gender: f, region: de}}\n")
    assert resolve_fish_voice(table, "LENA").id == ID_A
    assert resolve_fish_voice(table, ID_B).id == ID_B
    with pytest.raises(ValueError, match="Unbekannte Fish-Stimme 'nope'"):
        resolve_fish_voice(table, "nope")


@pytest.mark.parametrize("body, message", [
    ("voices:\n  x: {id: 'zu-kurz', label: X, gender: f, region: de}\n", "ID"),
    (f"voices:\n  x: {{id: '{ID_A}', label: X, gender: q, region: de}}\n", "gender"),
    ("nichts: 1\n", "voices"),
])
def test_invalid_tables_are_rejected_in_german(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        _table(tmp_path, body)


def test_voice_specs_resolve_fish_names_and_get_a_readable_slug(tmp_path):
    (tmp_path / "casting").mkdir()
    (tmp_path / "casting" / "fish_voices.yaml").write_text(
        f"voices:\n  lena: {{id: '{ID_A}', label: Lena, gender: f, region: de}}\n", encoding="utf-8")
    voices = tmp_path / "voices.yaml"
    voices.write_text("- {engine: fish, voice: lena}\n- {engine: kitten, voice: German}\n", encoding="utf-8")
    fish, kitten = load_voice_specs(voices, tmp_path)
    assert fish.voice == ID_A and fish.slug == "lena" and kitten.slug == "german"


def test_label_beats_voice_for_the_slug():
    assert VoiceSpec("fish", voice="x" * 32, label="Lena").slug == "lena"
```

- [ ] **Step 3: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_fish_voices.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.fish_voices`).

- [ ] **Step 4: Implementieren**

`generator/drova_voice/fish_voices.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_ID_RE = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True)
class FishVoice:
    key: str
    id: str
    label: str
    gender: str
    region: str


def load_fish_voices(path: Path) -> dict[str, FishVoice]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    voices = raw.get("voices") if isinstance(raw, dict) else None
    if not isinstance(voices, dict) or not voices:
        raise ValueError(f"{path}: Abschnitt 'voices' fehlt oder ist leer")
    table = {}
    for key, v in voices.items():
        vid = str(v.get("id", ""))
        if not _ID_RE.fullmatch(vid):
            raise ValueError(f"{path}: Stimme '{key}' hat keine gültige ID (32 Hex-Zeichen erwartet)")
        if v.get("gender") not in ("m", "f"):
            raise ValueError(f"{path}: Stimme '{key}': gender muss 'm' oder 'f' sein")
        table[str(key).lower()] = FishVoice(str(key).lower(), vid, str(v.get("label", key)), v["gender"], str(v.get("region", "de")))
    return table


def resolve_fish_voice(table: dict[str, FishVoice], name_or_id: str) -> FishVoice:
    if name_or_id.lower() in table:
        return table[name_or_id.lower()]
    if _ID_RE.fullmatch(name_or_id):
        return FishVoice(name_or_id[:8], name_or_id, name_or_id, "?", "?")
    raise ValueError(f"Unbekannte Fish-Stimme '{name_or_id}' (Name aus casting/fish_voices.yaml oder 32-stellige ID)")
```

In `generator/drova_voice/bakeoff.py`: `VoiceSpec` um das Feld erweitern und `slug` anpassen:

```python
@dataclass(frozen=True)
class VoiceSpec:
    engine: str
    voice: str | None = None
    reference: str | None = None
    label: str | None = None

    @property
    def slug(self) -> str:
        base = self.label or self.voice or (Path(self.reference).stem if self.reference else "default")
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "default"
```

`load_voice_specs` ersetzen:

```python
def load_voice_specs(path: Path, repo_root: Path) -> list[VoiceSpec]:
    from drova_voice.fish_voices import load_fish_voices, resolve_fish_voice

    table = None
    specs = []
    for item in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []:
        ref = item.get("reference")
        if ref and not Path(ref).is_absolute():
            ref = str((Path(repo_root) / ref).resolve())
        voice, label = item.get("voice"), None
        if item["engine"] == "fish" and voice:
            if table is None:
                table = load_fish_voices(Path(repo_root) / "casting" / "fish_voices.yaml")
            found = resolve_fish_voice(table, str(voice))
            voice, label = found.id, found.key
        specs.append(VoiceSpec(item["engine"], voice, ref, label))
    _check_unique_slugs(specs)
    return specs
```

- [ ] **Step 5: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add casting/fish_voices.yaml generator/drova_voice/fish_voices.py generator/drova_voice/bakeoff.py generator/tests/test_fish_voices.py
git commit -m "Add the official Fish voice table and resolve voice names" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Durchsatz- und Limit-Messung mit Fish (braucht das Ja des Nutzers)

**Files:**
- Create: `generator/fish_probe_voices.yaml`, `docs/decisions/2026-10-fish-throughput.md`

**Interfaces:**
- Consumes: `drova-voice bakeoff select|run` (Plan 1), Worker `fish` (Task 2), Tabelle (Task 3).
- Produces: gemessene Werte (Fehlerquote, Echtzeitfaktor, Zeilen pro Minute, Zeichen pro Minute) als Grundlage für die Entscheidung über Parallelität und Kosten in Plan 3.

- [ ] **Step 1: Freigabe beim Nutzer einholen (Hauptsitzung, nicht Subagent)**

Vorlegen und auf ein klares "ja" warten: Es werden **ca. 500 echte Spielzeilen als Text an api.fish.audio gesendet** (Stichprobe aus den `.loc`-Dateien, Stimme Lena, Modell `s2.1-pro-free`). Fish darf Inhalte laut Terms zur Modellverbesserung nutzen. Der Schlüssel kommt aus `FISH_API_KEY` in der Shell des Nutzers; ein im Chat gezeigter Schlüssel ist vorher zurückzusetzen und neu zu erzeugen.

- [ ] **Step 2: Stimmendatei anlegen** (`generator/fish_probe_voices.yaml`)

```yaml
# Messlauf für Durchsatz und Limits; Stimme per Name aus casting/fish_voices.yaml.
- {engine: fish, voice: lena}
```

- [ ] **Step 3: Stichprobe ziehen und erzeugen**

Run (Bash; `FISH_API_KEY` ist in der Umgebung gesetzt, nicht in der Befehlszeile):
```bash
cd generator
.venv/Scripts/drova-voice bakeoff select --per-bucket 55
.venv/Scripts/drova-voice bakeoff run --voices fish_probe_voices.yaml --engine fish
```
Expected: `Hörseite: …/out/bakeoff/index.html`, höchstens einzelne `FEHLER`-Zeilen. Bei vielen `HTTP 429` den Lauf mit weniger Zeilen wiederholen und die Grenze notieren. (`select` überschreibt die frühere Stichprobe; die alten Hörtest-Dateien bleiben als veraltet markiert.)

- [ ] **Step 4: Auswerten**

Run:
```bash
cd .. && python -I - <<'EOF'
import json, pathlib
rows = [json.loads(l) for l in pathlib.Path("out/bakeoff/results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
fish = [r for r in rows if r["engine"] == "fish"]
ok = [r for r in fish if r["ok"] and r["seconds"] > 0]
audio = sum(r["duration"] for r in ok); calc = sum(r["seconds"] for r in ok)
print(len(fish), "Zeilen,", len(fish) - len(ok), "Fehler/übersprungen; Audio", round(audio), "s; Rechenzeit", round(calc), "s; RTF", round(calc / audio, 2) if audio else None)
print("Hochrechnung 22 h Audio:", round(22 * calc / audio, 1) if audio else None, "h sequentiell")
EOF
```

- [ ] **Step 5: Ergebnis festhalten** (`docs/decisions/2026-10-fish-throughput.md`)

Die Datei enthält: Datum, Modell, Anzahl Zeilen, Fehler nach Statuscode, Echtzeitfaktor, Hochrechnung für 22 h, beobachtete Limits (Statuscodes, Wartezeiten), und die Frage an den Nutzer zu Kosten bzw. Tarif. Nur Zahlen und Statuscodes, keine Spieltexte.

- [ ] **Step 6: Commit**

```bash
git add generator/fish_probe_voices.yaml docs/decisions/2026-10-fish-throughput.md
git commit -m "Record the Fish throughput and limit measurement" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

# Teil B: Export (M1)

### Task 5: Zeilenkategorien und GVAR-Erkennung (`DrovaVoice.Core`)

**Files:**
- Create: `mod/DrovaVoice.Core/LineClassifier.cs`
- Test: `mod/DrovaVoice.Core.Tests/LineClassifierTests.cs`

**Interfaces:**
- Consumes: nichts.
- Produces: `enum LineCategory { Dialog, Player, Bark, Letter }`; `LineClassifier.IsGenericActor(string?) -> bool` (exakter Name, ohne Beachtung der Schreibung), `IsPlayerActor(string?) -> bool` (enthält "Player"), `IsBarkTree(string?) -> bool`, `Classify(string? treeName, string? actorName) -> LineCategory`, `CategoryName(LineCategory) -> string` (klein geschrieben: `dialog`, `player`, `bark`, `letter`), `ExtractGvars(string?) -> IReadOnlyList<string>` (Reihenfolge, ohne Duplikate, Name ohne `$GVAR:` und `$`).

- [ ] **Step 1: Failing Tests schreiben** (`LineClassifierTests.cs`)

```csharp
using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class LineClassifierTests
    {
        [Theory]
        [InlineData("NPC", true)]
        [InlineData("npc", true)]
        [InlineData("TEACHER", true)]
        [InlineData("Participant", true)]
        [InlineData("INSTIGATOR", true)]
        [InlineData("DRUID", true)]
        [InlineData("ACTOR", true)]
        [InlineData("Testfrau", false)]
        [InlineData("", false)]
        [InlineData(null, false)]
        public void Generic_actors_are_recognised_by_exact_name(string? name, bool expected)
            => Assert.Equal(expected, LineClassifier.IsGenericActor(name));

        [Theory]
        [InlineData("Player", true)]
        [InlineData("player", true)]
        [InlineData("Testfrau", false)]
        [InlineData(null, false)]
        public void Player_actor_is_recognised(string? name, bool expected)
            => Assert.Equal(expected, LineClassifier.IsPlayerActor(name));

        [Theory]
        [InlineData("DT_World_Test_Market", true)]
        [InlineData("DT_Generic_Combat_Bandit", true)]
        [InlineData("DT_Comment_Smith", true)]
        [InlineData("DT_Quest_X_WorldDialogue", true)]
        [InlineData("DT_Quest_X_WorldDialogues", true)]
        [InlineData("DT_Main_NPC_Test", false)]
        [InlineData("DT_Main_NPC_Test_Worldly", false)]
        [InlineData("", false)]
        [InlineData(null, false)]
        public void Bark_trees_follow_the_naming_rules(string? tree, bool expected)
            => Assert.Equal(expected, LineClassifier.IsBarkTree(tree));

        [Theory]
        [InlineData("DT_Main_NPC_Test", "Testfrau", LineCategory.Dialog)]
        [InlineData("DT_Main_NPC_Test", "Player", LineCategory.Player)]
        [InlineData("DT_World_Test_Market", "Testfrau", LineCategory.Bark)]
        [InlineData("DT_World_Test_Market", "Player", LineCategory.Player)]
        [InlineData("DT_Generic_Combat_Bandit", "NPC", LineCategory.Bark)]
        public void Classify_puts_the_player_first_then_barks(string tree, string actor, LineCategory expected)
            => Assert.Equal(expected, LineClassifier.Classify(tree, actor));

        [Fact]
        public void Category_names_are_lowercase()
        {
            Assert.Equal("dialog", LineClassifier.CategoryName(LineCategory.Dialog));
            Assert.Equal("player", LineClassifier.CategoryName(LineCategory.Player));
            Assert.Equal("bark", LineClassifier.CategoryName(LineCategory.Bark));
            Assert.Equal("letter", LineClassifier.CategoryName(LineCategory.Letter));
        }

        [Fact]
        public void Gvars_are_listed_in_order_without_duplicates()
        {
            var found = LineClassifier.ExtractGvars("Hallo $GVAR:EVars_Player.Name$, du hast $GVAR:EVars_Test.Gold$ und $GVAR:EVars_Player.Name$.");
            Assert.Equal(new List<string> { "EVars_Player.Name", "EVars_Test.Gold" }, found);
            Assert.Empty(LineClassifier.ExtractGvars("Kein Platzhalter hier."));
            Assert.Empty(LineClassifier.ExtractGvars(null));
        }
    }
}
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -c Release`
Expected: FAIL beim Bauen (`LineClassifier` existiert nicht).

- [ ] **Step 3: Implementieren** (`mod/DrovaVoice.Core/LineClassifier.cs`)

```csharp
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace DrovaVoice.Core
{
    public enum LineCategory { Dialog, Player, Bark, Letter }

    public static class LineClassifier
    {
        private static readonly string[] GenericActors = { "NPC", "TEACHER", "INSTIGATOR", "DRUID", "Participant", "ACTOR" };
        private static readonly Regex GvarRegex = new Regex(@"\$GVAR:([^$]+)\$", RegexOptions.Compiled);

        public static bool IsGenericActor(string? actorName)
        {
            if (string.IsNullOrEmpty(actorName)) return false;
            foreach (var generic in GenericActors)
                if (string.Equals(generic, actorName, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public static bool IsPlayerActor(string? actorName)
            => !string.IsNullOrEmpty(actorName) && actorName.Contains("Player", StringComparison.OrdinalIgnoreCase);

        public static bool IsBarkTree(string? treeName)
        {
            if (string.IsNullOrEmpty(treeName)) return false;
            return treeName.StartsWith("DT_World", StringComparison.Ordinal)
                || treeName.StartsWith("DT_Generic_Combat_", StringComparison.Ordinal)
                || treeName.StartsWith("DT_Comment_", StringComparison.Ordinal)
                || treeName.EndsWith("_WorldDialogue", StringComparison.Ordinal)
                || treeName.EndsWith("_WorldDialogues", StringComparison.Ordinal);
        }

        public static LineCategory Classify(string? treeName, string? actorName)
        {
            if (IsPlayerActor(actorName)) return LineCategory.Player;
            return IsBarkTree(treeName) ? LineCategory.Bark : LineCategory.Dialog;
        }

        public static string CategoryName(LineCategory category) => category.ToString().ToLowerInvariant();

        public static IReadOnlyList<string> ExtractGvars(string? text)
        {
            var result = new List<string>();
            if (string.IsNullOrEmpty(text)) return result;
            foreach (Match m in GvarRegex.Matches(text))
            {
                var name = m.Groups[1].Value;
                if (!result.Contains(name)) result.Add(name);
            }
            return result;
        }
    }
}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -c Release`
Expected: alle Tests grün (12 bisherige plus die neuen).

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice.Core/LineClassifier.cs mod/DrovaVoice.Core.Tests/LineClassifierTests.cs
git commit -m "Add line category rules and GVAR detection to the core library" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Manifest-Format (`DrovaVoice.Core`)

**Files:**
- Create: `mod/DrovaVoice.Core/Manifest.cs`
- Test: `mod/DrovaVoice.Core.Tests/ManifestTests.cs`

**Interfaces:**
- Consumes: nichts (IDs bildet der Aufrufer mit `LineIds`).
- Produces: `ManifestLine` (Eigenschaften `Id, Tree, NodeId, NodeType, ChoiceIndex?, ActorName, Category, Generic, LocaPath, LocaKey, Text, Gvars, Next, Prev`), `Manifest` (`Version`, `Language`, `Lines`), `ManifestJson.Serialize(Manifest) -> string` (camelCase, Umlaute unmaskiert, `null` weggelassen), `ManifestJson.Deserialize(string) -> Manifest`. Das JSON-Format ist die Schnittstelle zu Python (`export_report.py`, Task 7): Felder `version`, `language`, `lines[]` mit `locaPath`, `locaKey`, `id`, `category`, `generic`, `text`.

- [ ] **Step 1: Failing Tests schreiben** (`ManifestTests.cs`)

```csharp
using System.Text.Json;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ManifestTests
    {
        private static Manifest Sample() => new Manifest
        {
            Language = "de",
            Lines =
            {
                new ManifestLine { Id = "DT_Main_NPC_Test|Dialog/NPC_Test|Plh_1", Tree = "DT_Main_NPC_Test", NodeId = 3, NodeType = "statement",
                    ActorName = "Testfrau", Category = "dialog", LocaPath = "Dialog/NPC_Test", LocaKey = "Plh_1", Text = "Schön, dass du da bist.",
                    Gvars = { "EVars_Player.Name" }, Next = { 4 }, Prev = { 2 } },
                new ManifestLine { Id = "DT_Main_NPC_Test|Dialog/NPC_Test|Plh_2|c1", Tree = "DT_Main_NPC_Test", NodeId = 4, NodeType = "choice",
                    ChoiceIndex = 1, ActorName = "Player", Category = "player", Generic = false, LocaPath = "Dialog/NPC_Test", LocaKey = "Plh_2", Text = "Ja." },
            },
        };

        [Fact]
        public void Serialized_json_uses_the_documented_field_names_and_raw_umlauts()
        {
            var json = ManifestJson.Serialize(Sample());
            Assert.Contains("\"locaPath\":\"Dialog/NPC_Test\"", json);
            Assert.Contains("\"nodeType\":\"statement\"", json);
            Assert.Contains("Schön", json);
            Assert.DoesNotContain("\\u00F6", json);
        }

        [Fact]
        public void A_missing_choice_index_is_omitted_but_a_present_one_is_written()
        {
            var json = ManifestJson.Serialize(Sample());
            Assert.Equal(1, System.Text.RegularExpressions.Regex.Matches(json, "choiceIndex").Count);
            Assert.Contains("\"choiceIndex\":1", json);
        }

        [Fact]
        public void Roundtrip_keeps_every_field()
        {
            var back = ManifestJson.Deserialize(ManifestJson.Serialize(Sample()));
            Assert.Equal("de", back.Language);
            Assert.Equal(2, back.Lines.Count);
            var first = back.Lines[0];
            Assert.Equal("Schön, dass du da bist.", first.Text);
            Assert.Equal(new[] { "EVars_Player.Name" }, first.Gvars);
            Assert.Equal(new[] { 4 }, first.Next);
            Assert.Equal(new[] { 2 }, first.Prev);
            Assert.Null(first.ChoiceIndex);
            Assert.Equal(1, back.Lines[1].ChoiceIndex);
        }

        [Fact]
        public void Invalid_json_throws_a_json_exception()
            => Assert.ThrowsAny<JsonException>(() => ManifestJson.Deserialize("{ das ist kein json"));
    }
}
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -c Release`
Expected: FAIL beim Bauen (`Manifest` existiert nicht).

- [ ] **Step 3: Implementieren** (`mod/DrovaVoice.Core/Manifest.cs`)

```csharp
using System.Collections.Generic;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DrovaVoice.Core
{
    public sealed class ManifestLine
    {
        public string Id { get; set; } = "";
        public string Tree { get; set; } = "";
        public int NodeId { get; set; }
        public string NodeType { get; set; } = "statement";
        public int? ChoiceIndex { get; set; }
        public string ActorName { get; set; } = "";
        public string Category { get; set; } = "dialog";
        public bool Generic { get; set; }
        public string LocaPath { get; set; } = "";
        public string LocaKey { get; set; } = "";
        public string Text { get; set; } = "";
        public List<string> Gvars { get; set; } = new List<string>();
        public List<int> Next { get; set; } = new List<int>();
        public List<int> Prev { get; set; } = new List<int>();
    }

    public sealed class Manifest
    {
        public int Version { get; set; } = 1;
        public string Language { get; set; } = "de";
        public List<ManifestLine> Lines { get; set; } = new List<ManifestLine>();
    }

    public static class ManifestJson
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            WriteIndented = false,
        };

        public static string Serialize(Manifest manifest) => JsonSerializer.Serialize(manifest, Options);

        public static Manifest Deserialize(string json)
            => JsonSerializer.Deserialize<Manifest>(json, Options) ?? throw new JsonException("Manifest ist leer");
    }
}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -c Release`
Expected: alle grün.

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice.Core/Manifest.cs mod/DrovaVoice.Core.Tests/ManifestTests.cs
git commit -m "Add the manifest format to the core library" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Abdeckungsbericht (Python)

**Files:**
- Create: `generator/drova_voice/export_report.py`
- Modify: `generator/drova_voice/cli.py`
- Test: `generator/tests/test_export_report.py`

**Interfaces:**
- Consumes: `parse_loc(content) -> LocParseResult(entries[LocEntry(key, text, line)], errors)` aus `drova_voice.loc`; `normalize_loca_path(path)` aus `drova_voice.ids`; `Config(game_dir, language, repo_root)` mit `loc_dir`, `data_dir`.
- Produces: `in_scope(rel: Path) -> bool`; `loca_path_of(file, loc_dir, language) -> str`; `Coverage(total, covered, missing: tuple[str, ...], extra, by_folder: dict[str, tuple[int, int]])` mit Eigenschaft `percent`; `compute_coverage(manifest: dict, loc_dir: Path, language: str) -> Coverage`; `format_report(cov, missing_path) -> str`; CLI `drova-voice export report [--manifest PFAD] [--min-coverage 98]` (Exit 0 bei >= Schwelle, 1 darunter, 2 bei fehlendem Manifest) und `drova-voice export fetch` (kopiert `<Spiel>/Mods/DrovaVoice/Export/<lang>/` nach `data/export/<lang>/`).

- [ ] **Step 1: Failing Tests schreiben** (`generator/tests/test_export_report.py`; erfundene Einträge)

```python
import json
from pathlib import Path

import pytest

from drova_voice.cli import main
from drova_voice.export_report import compute_coverage, format_report, in_scope, loca_path_of


def _loc(root: Path, rel: str, keys: list[str]):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(f"{k} {{ Erfundener Text {i}. }}" for i, k in enumerate(keys)) + "\n", encoding="utf-8")


def _line(path: str, key: str):
    return {"id": f"DT_Test|{path}|{key}", "locaPath": path, "locaKey": key, "category": "dialog"}


@pytest.fixture
def loc_dir(tmp_path):
    d = tmp_path / "Localization" / "de"
    _loc(d, "Dialog/NPC_A_de.loc", ["Plh_1", "Plh_2", "Plh_3", "Plh_4"])
    _loc(d, "Dialogues/Quest_B_de.loc", ["Plh_1"])
    _loc(d, "IntroWorldDialog_de.loc", ["W_1"])
    _loc(d, "Letters/Brief_de.loc", ["L_1"])       # außerhalb des Umfangs
    _loc(d, "Items_de.loc", ["Sword_name"])        # außerhalb des Umfangs
    return d


def test_scope_covers_dialog_folders_and_world_files_only():
    assert in_scope(Path("Dialog/NPC_A_de.loc")) and in_scope(Path("Dialogues/Q_de.loc")) and in_scope(Path("Dialogue/Q_de.loc"))
    assert in_scope(Path("IntroWorldDialog_de.loc")) and in_scope(Path("Sub/Foo_World_de.loc"))
    assert not in_scope(Path("Letters/Brief_de.loc")) and not in_scope(Path("Items_de.loc"))


def test_loca_path_drops_extension_and_language_suffix(loc_dir):
    assert loca_path_of(loc_dir / "Dialog" / "NPC_A_de.loc", loc_dir, "de") == "Dialog/NPC_A"
    assert loca_path_of(loc_dir / "IntroWorldDialog_de.loc", loc_dir, "de") == "IntroWorldDialog"


def test_coverage_counts_covered_missing_and_extra(loc_dir):
    manifest = {"lines": [_line("Dialog/NPC_A", "Plh_1"), _line("Dialog/NPC_A", "Plh_2"), _line("Dialog/NPC_A", "Plh_3"),
                          _line("Dialogues/Quest_B", "Plh_1"), _line("Dialog/NPC_A", "Plh_99")]}
    cov = compute_coverage(manifest, loc_dir, "de")
    assert (cov.total, cov.covered, cov.extra) == (6, 4, 1)
    assert cov.percent == pytest.approx(100 * 4 / 6)
    assert cov.missing == ("Dialog/NPC_A:Plh_4", "IntroWorldDialog:W_1")
    assert cov.by_folder["Dialog"] == (4, 3)


def test_paths_are_compared_normalised(loc_dir):
    manifest = {"lines": [_line("Dialog\\NPC_A/", "Plh_1")]}
    assert compute_coverage(manifest, loc_dir, "de").covered == 1


def test_empty_scope_is_fully_covered(tmp_path):
    (tmp_path / "de").mkdir()
    assert compute_coverage({"lines": []}, tmp_path / "de", "de").percent == 100.0


def test_report_text_names_the_numbers_and_the_missing_file(loc_dir, tmp_path):
    cov = compute_coverage({"lines": [_line("Dialog/NPC_A", "Plh_1")]}, loc_dir, "de")
    text = format_report(cov, tmp_path / "coverage_missing.txt")
    assert "Abdeckung" in text and "1 von 6" in text and "coverage_missing.txt" in text


def _repo(tmp_path, loc_dir_game):
    gen = tmp_path / "repo" / "generator"
    gen.mkdir(parents=True)
    cfg = gen / "config.yaml"
    cfg.write_text(f'game_dir: "{loc_dir_game.as_posix()}"\n', encoding="utf-8")
    return tmp_path / "repo", cfg


def _game_with_loc(tmp_path, loc_dir):
    game = tmp_path / "game"
    target = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de"
    target.parent.mkdir(parents=True)
    loc_dir.rename(target)
    return game


def test_cli_report_returns_1_below_threshold_and_writes_the_missing_list(tmp_path, loc_dir, capsys):
    repo, cfg = _repo(tmp_path, _game_with_loc(tmp_path, loc_dir))
    manifest = repo / "data" / "export" / "de" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"lines": [_line("Dialog/NPC_A", "Plh_1")]}), encoding="utf-8")
    assert main(["--config", str(cfg), "export", "report"]) == 1
    assert (manifest.parent / "coverage_missing.txt").read_text(encoding="utf-8").count("\n") == 5
    assert main(["--config", str(cfg), "export", "report", "--min-coverage", "10"]) == 0
    assert "Abdeckung" in capsys.readouterr().out


def test_cli_report_without_manifest_exits_2(tmp_path, loc_dir, capsys):
    repo, cfg = _repo(tmp_path, _game_with_loc(tmp_path, loc_dir))
    assert main(["--config", str(cfg), "export", "report"]) == 2
    assert "Manifest nicht gefunden" in capsys.readouterr().err


def test_cli_fetch_copies_the_export_folder_from_the_game(tmp_path, loc_dir, capsys):
    game = _game_with_loc(tmp_path, loc_dir)
    repo, cfg = _repo(tmp_path, game)
    src = game / "Mods" / "DrovaVoice" / "Export" / "de"
    src.mkdir(parents=True)
    (src / "manifest.json").write_text('{"lines": []}', encoding="utf-8")
    assert main(["--config", str(cfg), "export", "fetch"]) == 0
    assert (repo / "data" / "export" / "de" / "manifest.json").read_text(encoding="utf-8") == '{"lines": []}'
    assert main(["--config", str(cfg), "export", "fetch"]) == 0  # wiederholbar
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_export_report.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.export_report`).

- [ ] **Step 3: Modul schreiben** (`generator/drova_voice/export_report.py`)

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drova_voice.ids import normalize_loca_path
from drova_voice.loc import parse_loc


def in_scope(rel: Path) -> bool:
    """Umfang laut Spec §5: Dialog*/ (inkl. Dialogues/), sowie *World*.loc."""
    return rel.parts[0].startswith("Dialog") or "World" in rel.name


def loca_path_of(file: Path, loc_dir: Path, language: str) -> str:
    rel = file.relative_to(loc_dir).with_suffix("").as_posix()
    suffix = f"_{language}"
    if rel.endswith(suffix):
        rel = rel[: -len(suffix)]
    return normalize_loca_path(rel)


@dataclass(frozen=True)
class Coverage:
    total: int
    covered: int
    missing: tuple[str, ...]
    extra: int
    by_folder: dict[str, tuple[int, int]]

    @property
    def percent(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 100.0


def compute_coverage(manifest: dict, loc_dir: Path, language: str) -> Coverage:
    in_manifest = {(normalize_loca_path(l["locaPath"]), l["locaKey"]) for l in manifest.get("lines", [])}
    wanted: set[tuple[str, str]] = set()
    folder_of: dict[tuple[str, str], str] = {}
    for file in sorted(Path(loc_dir).rglob("*.loc")):
        rel = file.relative_to(loc_dir)
        if not in_scope(rel):
            continue
        path = loca_path_of(file, loc_dir, language)
        folder = rel.parts[0] if len(rel.parts) > 1 else "(Wurzel)"
        for entry in parse_loc(file.read_text(encoding="utf-8-sig", errors="replace")).entries:
            wanted.add((path, entry.key))
            folder_of[(path, entry.key)] = folder
    missing = tuple(f"{p}:{k}" for p, k in sorted(wanted - in_manifest))
    by_folder: dict[str, tuple[int, int]] = {}
    for item in wanted:
        total, covered = by_folder.get(folder_of[item], (0, 0))
        by_folder[folder_of[item]] = (total + 1, covered + (item in in_manifest))
    return Coverage(len(wanted), len(wanted & in_manifest), missing, len(in_manifest - wanted), by_folder)


def format_report(cov: Coverage, missing_path: Path) -> str:
    lines = [f"Abdeckung: {cov.percent:.2f} % ({cov.covered} von {cov.total} Einträgen im Manifest)",
             f"Zeilen im Manifest ohne .loc-Eintrag: {cov.extra}"]
    for folder, (total, covered) in sorted(cov.by_folder.items()):
        lines.append(f"  {folder}: {covered} von {total}")
    lines.append(f"Fehlende Einträge ({len(cov.missing)}): {missing_path}")
    return "\n".join(lines)
```

- [ ] **Step 4: CLI erweitern** (`generator/drova_voice/cli.py`)

Imports ergänzen: `import json`, `import shutil` und `from drova_voice.export_report import compute_coverage, format_report`.

In `_parse` nach dem `smoke`-Parser:

```python
    exp = sub.add_parser("export", help="Export-Ergebnis der Mod prüfen").add_subparsers(dest="ecmd", required=True)
    rep = exp.add_parser("report", help="Abdeckung des Manifests gegen die .loc-Dateien")
    rep.add_argument("--manifest", type=Path)
    rep.add_argument("--min-coverage", type=float, default=98.0)
    exp.add_parser("fetch", help="Export-Ordner aus dem Spielordner nach data/export kopieren")
```

In `_run` direkt vor `if args.bcmd == "select":` einfügen:

```python
    if args.cmd == "export":
        export_dir = cfg.data_dir / "export" / cfg.language
        if args.ecmd == "fetch":
            src = cfg.game_dir / "Mods" / "DrovaVoice" / "Export" / cfg.language
            if not src.is_dir():
                print(f"FEHLER: Export-Ordner nicht gefunden: {src} (Export im Spiel auslösen, siehe docs/export.md)", file=sys.stderr)
                return 2
            export_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, export_dir, dirs_exist_ok=True)
            print(f"{src} -> {export_dir}")
            return 0
        manifest_path = args.manifest or (export_dir / "manifest.json")
        if not manifest_path.is_file():
            print(f"FEHLER: Manifest nicht gefunden: {manifest_path} (Export im Spiel auslösen, siehe docs/export.md)", file=sys.stderr)
            return 2
        cov = compute_coverage(json.loads(manifest_path.read_text(encoding="utf-8-sig")), cfg.loc_dir, cfg.language)
        missing_path = manifest_path.with_name("coverage_missing.txt")
        missing_path.write_text("".join(f"{m}\n" for m in cov.missing), encoding="utf-8")
        print(format_report(cov, missing_path))
        return 0 if cov.percent >= args.min_coverage else 1
```

- [ ] **Step 5: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/export_report.py generator/drova_voice/cli.py generator/tests/test_export_report.py
git commit -m "Add the export coverage report and fetch command" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Mod: Export der geladenen Bäume (im Spiel prüfen)

**Files:**
- Modify: `mod/DrovaVoice/DrovaVoice.csproj`, `mod/DrovaVoice/DrovaVoiceMod.cs`
- Create: `mod/DrovaVoice/Export/DialogueExporter.cs`, `mod/DrovaVoice/Export/TreeSource.cs`, `mod/DrovaVoice/Export/ManifestFile.cs`

**Interfaces:**
- Consumes: `LineIds.Statement(tree, locaPath, locaKey)`, `LineIds.Choice(tree, locaPath, locaKey, choiceIndex)`, `LineClassifier`, `Manifest`, `ManifestLine`, `ManifestJson` (Tasks 5, 6; `LineIds` aus Plan 1). Spielklassen (verifiziert gegen die Assemblies): `DialogueTree` (`name`, `LocaPath`, `allNodes`, `IsTestOrDebugDialogue`, `SelfDeserialize()`, `DeserializeIfNotDoneYet(bool)`), `Node` (`ID`, `inConnections`, `outConnections`; `Connection.sourceNode`/`targetNode`), `DS_StatementNode` (`statement` mit `locaKey`, `useGlobalLoca`, `GlobalLocaPath`; `actorName`; `GetLocalizedString()`), `DS_MultipleChoiceNode` (`availableChoices`, `actorName`, `GetLocalizedString(DS_Statement)`).
- Produces: `DialogueExporter(string language, MelonLogger.Instance log)` mit `Export(IEnumerable<DialogueTree>) -> Manifest` und `ExportStats`; `TreeSource.LoadedTrees()`; `ManifestFile.Save(Manifest, string path)` (atomar über `.tmp`); Auslöser: Datei `<Spiel>/Mods/DrovaVoice/export.trigger` (wird beim Erkennen gelöscht) oder Taste F9; Ausgabe `<Spiel>/Mods/DrovaVoice/Export/<lang>/manifest.json`.

- [ ] **Step 1: Referenzen im Mod-Projekt ergänzen** (`mod/DrovaVoice/DrovaVoice.csproj`, im `ItemGroup` mit den `Reference`-Einträgen)

```xml
    <Reference Include="$(DrovaGameDir)\MelonLoader\Il2CppAssemblies\*.dll" Private="false" />
```

Prüfen, dass die Unity-Module dort liegen:
```bash
ls "/d/Games/Steam/steamapps/common/Drova - Forsaken Kin/MelonLoader/Il2CppAssemblies" | grep -E "^(Il2CppDrova|Il2CppParadoxNotion|Il2Cppmscorlib|UnityEngine\.CoreModule|UnityEngine\.InputLegacyModule)\.dll$"
```
Expected: fünf Zeilen. Treten beim Bauen `CS0433`/`CS0436`-Mehrdeutigkeiten auf, den Platzhalter durch die Einzelreferenzen dieser fünf DLLs ersetzen (je `<Reference Include="Name"><HintPath>…</HintPath><Private>false</Private></Reference>`).

- [ ] **Step 2: Exporter schreiben** (`mod/DrovaVoice/Export/DialogueExporter.cs`)

```csharp
using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Il2CppNodeCanvas.DialogueTrees;
using Il2CppNodeCanvas.Framework;
using MelonLoader;

namespace DrovaVoice.Export
{
    public sealed class ExportStats
    {
        public int Trees, TreesFailed, TreesSkipped, Statements, Choices, SkippedUnused, SkippedDuplicates, SkippedInvalid;
        public override string ToString()
            => $"Bäume {Trees} (fehlgeschlagen {TreesFailed}, übersprungen {TreesSkipped}); Aussagen {Statements}, Optionen {Choices}; "
             + $"ohne Text/unbenutzt {SkippedUnused}, doppelt {SkippedDuplicates}, ungültige ID {SkippedInvalid}";
    }

    public sealed class DialogueExporter
    {
        private const string KeyMissingPrefix = "[LOCA] Key not found";
        private readonly string _language;
        private readonly MelonLogger.Instance _log;
        public ExportStats Stats { get; } = new ExportStats();

        public DialogueExporter(string language, MelonLogger.Instance log)
        {
            _language = language;
            _log = log;
        }

        public Manifest Export(IEnumerable<DialogueTree> trees)
        {
            var manifest = new Manifest { Language = _language };
            var seen = new HashSet<string>();
            foreach (var tree in trees)
            {
                if (tree == null) continue;
                try
                {
                    if (tree.IsTestOrDebugDialogue) { Stats.TreesSkipped++; continue; }
                    ExportTree(tree, manifest.Lines, seen);
                    Stats.Trees++;
                }
                catch (Exception e)
                {
                    Stats.TreesFailed++;
                    _log.Warning($"Baum {SafeName(tree)} nicht exportiert: {e.GetType().Name}: {e.Message}");
                }
            }
            _log.Msg("Export fertig: " + Stats + $"; Zeilen im Manifest {manifest.Lines.Count}");
            return manifest;
        }

        private static string SafeName(DialogueTree tree)
        {
            try { return tree.name; } catch { return "?"; }
        }

        private void ExportTree(DialogueTree tree, List<ManifestLine> lines, HashSet<string> seen)
        {
            tree.SelfDeserialize();
            tree.DeserializeIfNotDoneYet(true);
            string treeName = tree.name;
            string treeLoca = tree.LocaPath ?? "";
            var nodes = tree.allNodes;
            for (int i = 0; i < nodes.Count; i++)
            {
                Node node = nodes[i];
                var statement = node.TryCast<DS_StatementNode>();
                if (statement != null) { AddStatement(treeName, treeLoca, statement, lines, seen); continue; }
                var choiceNode = node.TryCast<DS_MultipleChoiceNode>();
                if (choiceNode != null) AddChoices(treeName, treeLoca, choiceNode, lines, seen);
            }
        }

        private void AddStatement(string treeName, string treeLoca, DS_StatementNode node, List<ManifestLine> lines, HashSet<string> seen)
        {
            var st = node.statement;
            string key = st.locaKey;
            string locaPath = st.useGlobalLoca ? st.GlobalLocaPath : treeLoca;
            string text = node.GetLocalizedString();
            if (string.IsNullOrEmpty(key) || string.IsNullOrEmpty(text) || text.StartsWith(KeyMissingPrefix, StringComparison.Ordinal))
            {
                Stats.SkippedUnused++;
                return;
            }
            string actor = node.actorName ?? "";
            if (!TryAdd(lines, seen, LineIdsSafe(() => LineIds.Statement(treeName, locaPath, key)), treeName, node, "statement", null, actor, locaPath, key, text)) return;
            Stats.Statements++;
        }

        private void AddChoices(string treeName, string treeLoca, DS_MultipleChoiceNode node, List<ManifestLine> lines, HashSet<string> seen)
        {
            var choices = node.availableChoices;
            string actor = node.actorName ?? "";
            for (int k = 0; k < choices.Count; k++)
            {
                var choice = choices[k];
                var st = choice.statement;
                string key = st.locaKey;
                string locaPath = st.useGlobalLoca ? st.GlobalLocaPath : treeLoca;
                string text = node.GetLocalizedString(st);
                if (string.IsNullOrEmpty(key) || string.IsNullOrEmpty(text) || text.StartsWith(KeyMissingPrefix, StringComparison.Ordinal))
                {
                    Stats.SkippedUnused++;
                    continue;
                }
                int index = k;
                if (!TryAdd(lines, seen, LineIdsSafe(() => LineIds.Choice(treeName, locaPath, key, index)), treeName, node, "choice", k, actor, locaPath, key, text)) continue;
                Stats.Choices++;
            }
        }

        private static string? LineIdsSafe(Func<string> build)
        {
            try { return build(); } catch (ArgumentException) { return null; }
        }

        private bool TryAdd(List<ManifestLine> lines, HashSet<string> seen, string? id, string treeName, Node node, string nodeType,
                            int? choiceIndex, string actor, string locaPath, string key, string text)
        {
            if (id == null) { Stats.SkippedInvalid++; return false; }
            if (!seen.Add(id)) { Stats.SkippedDuplicates++; return false; }
            var line = new ManifestLine
            {
                Id = id, Tree = treeName, NodeId = node.ID, NodeType = nodeType, ChoiceIndex = choiceIndex, ActorName = actor,
                Category = LineClassifier.CategoryName(LineClassifier.Classify(treeName, actor)),
                Generic = LineClassifier.IsGenericActor(actor), LocaPath = LineIds.NormalizeLocaPath(locaPath), LocaKey = key, Text = text,
            };
            line.Gvars.AddRange(LineClassifier.ExtractGvars(text));
            for (int i = 0; i < node.outConnections.Count; i++) line.Next.Add(node.outConnections[i].targetNode.ID);
            for (int i = 0; i < node.inConnections.Count; i++) line.Prev.Add(node.inConnections[i].sourceNode.ID);
            lines.Add(line);
            return true;
        }
    }
}
```

- [ ] **Step 3: Baumquelle und Dateiausgabe** 

`mod/DrovaVoice/Export/TreeSource.cs`:

```csharp
using System.Collections.Generic;
using Il2CppNodeCanvas.DialogueTrees;
using UnityEngine;

namespace DrovaVoice.Export
{
    public static class TreeSource
    {
        /// <summary>Alle zurzeit im Speicher befindlichen Dialogbäume.</summary>
        public static IEnumerable<DialogueTree> LoadedTrees()
        {
            var trees = Resources.FindObjectsOfTypeAll<DialogueTree>();
            for (int i = 0; i < trees.Length; i++) yield return trees[i];
        }
    }
}
```

`mod/DrovaVoice/Export/ManifestFile.cs`:

```csharp
using System.IO;
using System.Text;
using DrovaVoice.Core;

namespace DrovaVoice.Export
{
    public static class ManifestFile
    {
        /// <summary>Schreibt erst in eine .tmp-Datei und ersetzt dann: nie eine halb geschriebene manifest.json.</summary>
        public static void Save(Manifest manifest, string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, ManifestJson.Serialize(manifest), new UTF8Encoding(false));
            File.Move(tmp, path, true);
        }
    }
}
```

- [ ] **Step 4: Auslöser in der Mod** (`mod/DrovaVoice/DrovaVoiceMod.cs` ersetzen)

```csharp
using System;
using System.IO;
using DrovaVoice.Core;
using DrovaVoice.Export;
using MelonLoader;
using MelonLoader.Utils;
using UnityEngine;

[assembly: MelonInfo(typeof(DrovaVoice.DrovaVoiceMod), "DrovaVoice", "0.1.0", "janphi001")]
[assembly: MelonGame("Just2D", "Drova")]
[assembly: MelonAdditionalDependencies("Drova_Modding_API")]

namespace DrovaVoice
{
    public sealed class DrovaVoiceMod : MelonMod
    {
        private MelonPreferences_Entry<string>? _language;
        private bool _exporting;
        private bool _hotkeyBroken;
        private int _frame;

        private string ModDir => Path.Combine(MelonEnvironment.ModsDirectory, "DrovaVoice");
        private string TriggerPath => Path.Combine(ModDir, "export.trigger");

        public override void OnInitializeMelon()
        {
            _language = MelonPreferences.CreateCategory("DrovaVoice").CreateEntry("ExportLanguage", "de", description: "Sprache des Exports (Ordnername)");
            Directory.CreateDirectory(ModDir);
            string probe = LineIds.AudioFileName(LineIds.Statement("DT_Main_NPC_Adela", "Dialog/NPC_Adela", "Plh_5"));
            LoggerInstance.Msg($"DrovaVoice {Info.Version} geladen (Core ok: {probe}). Export: Datei export.trigger in {ModDir} anlegen oder F9 drücken.");
        }

        public override void OnUpdate()
        {
            _frame++;
            bool trigger = false;
            if (_frame % 60 == 0 && File.Exists(TriggerPath))
            {
                try { File.Delete(TriggerPath); } catch (IOException) { }
                trigger = true;
            }
            if (!trigger && HotkeyPressed()) trigger = true;
            if (trigger) RunExport();
        }

        private bool HotkeyPressed()
        {
            if (_hotkeyBroken) return false;
            try { return Input.GetKeyDown(KeyCode.F9); }
            catch (Exception e)
            {
                _hotkeyBroken = true;
                LoggerInstance.Warning($"F9 nicht verfügbar ({e.GetType().Name}); nur die Trigger-Datei funktioniert.");
                return false;
            }
        }

        private void RunExport()
        {
            if (_exporting) { LoggerInstance.Warning("Export läuft bereits, Auslöser ignoriert."); return; }
            _exporting = true;
            try
            {
                string lang = _language!.Value;
                var exporter = new DialogueExporter(lang, LoggerInstance);
                var manifest = exporter.Export(TreeSource.LoadedTrees());
                string path = Path.Combine(ModDir, "Export", lang, "manifest.json");
                ManifestFile.Save(manifest, path);
                LoggerInstance.Msg($"Manifest geschrieben: {path} ({manifest.Lines.Count} Zeilen)");
            }
            catch (Exception e)
            {
                LoggerInstance.Error($"Export fehlgeschlagen: {e}");
            }
            finally
            {
                _exporting = false;
            }
        }
    }
}
```

- [ ] **Step 5: Bauen**

Run: `dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release`
Expected: Build erfolgreich, `Mods/DrovaVoice.dll` und `UserLibs/DrovaVoice.Core.dll` im Spielordner aktualisiert. Fehlt ein Member (`CS1061`), den echten Namen nachsehen:
```bash
dotnet "C:/Users/jpmin/AppData/Local/Temp/claude/D--Games-Projekte-DrovaTTAI/604cd5cf-b53a-4b77-934b-cdb345f04a39/scratchpad/typedump/out/typedump.dll" "D:/Games/Steam/steamapps/common/Drova - Forsaken Kin/MelonLoader/Il2CppAssemblies" '<TypName>' | grep -v Native
```
(Das Werkzeug liegt im Scratchpad der Sitzung; wenn es fehlt, ein Konsolenprojekt mit `System.Reflection.Metadata` schreiben, das `TypeDefinitions` mit Properties und Methoden ausgibt.) Anpassung im Commit-Text vermerken.

- [ ] **Step 6: Im Spiel prüfen (Nutzer startet das Spiel, Hauptmenü genügt)**

Der Nutzer startet Drova und wartet im Hauptmenü. Danach in der Hauptsitzung:
```bash
touch "/d/Games/Steam/steamapps/common/Drova - Forsaken Kin/Mods/DrovaVoice/export.trigger"
sleep 60
grep -E "DrovaVoice|Export" "/d/Games/Steam/steamapps/common/Drova - Forsaken Kin/MelonLoader/Latest.log" | tail -8
```
Expected: `Export fertig: Bäume …` und `Manifest geschrieben: …manifest.json (N Zeilen)`. Im Hauptmenü sind meist nur wenige Bäume geladen; die Zahl notieren. Danach `cd generator && .venv/Scripts/drova-voice export fetch && .venv/Scripts/drova-voice export report` ausführen und die Abdeckung im Ledger festhalten (Exit 1 ist hier erwartet).

- [ ] **Step 7: Commit**

```bash
git add mod/DrovaVoice
git commit -m "Add the dialogue exporter with a file trigger" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Mod: alle Bäume über den Addressables-Katalog laden (R1)

**Files:**
- Create: `mod/DrovaVoice.Core/CatalogReader.cs`, `mod/DrovaVoice/Export/CatalogTreeLoader.cs`
- Modify: `mod/DrovaVoice/DrovaVoiceMod.cs`
- Test: `mod/DrovaVoice.Core.Tests/CatalogReaderTests.cs`

**Interfaces:**
- Consumes: `Manifest`, `DialogueExporter` (Tasks 6, 8). Im Spielkatalog `Drova_Data/StreamingAssets/aa/catalog.json` liegen die Assetpfade in `m_InternalIds` (verifiziert: 25.636 Einträge, davon 1.806 `DT_*.asset`, teils unter `Assets/Editor/…`).
- Produces: `CatalogReader.TreeAddresses(string catalogJson) -> IReadOnlyList<string>` (Pfade, die auf `/DT_*.asset` enden und nicht unter `Assets/Editor/` liegen; Reihenfolge erhalten, ohne Duplikate); `CatalogTreeLoader.Load(IEnumerable<string> addresses, MelonLogger.Instance log) -> List<DialogueTree>`; zweiter Auslöser `export-all.trigger`.

- [ ] **Step 1: Failing Tests schreiben** (`CatalogReaderTests.cs`; erfundener Katalog)

```csharp
using System.Linq;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class CatalogReaderTests
    {
        private const string Catalog = @"{
          ""m_InternalIds"": [
            ""Assets/Content/Dialogue/DT_Main_NPC_Test.asset"",
            ""Assets/Editor/Resources/TestData/DT_World_Tests_X.asset"",
            ""Assets/Content/Dialogue/DT_Main_NPC_Test.asset"",
            ""Assets/Content/Dialogue/Readme.asset"",
            ""Assets/Content/Dialogue/DT_Quest_Test_WorldDialogues.asset"",
            ""Library/PackageCache/DT_Fremd.asset.bundle"",
            ""{UnityEngine.AddressableAssets.Addressables.RuntimePath}/StandaloneWindows64/x.bundle""
          ],
          ""m_KeyDataString"": ""AAAA""
        }";

        [Fact]
        public void Only_dialogue_tree_assets_outside_the_editor_folder_are_listed_once_in_order()
        {
            var found = CatalogReader.TreeAddresses(Catalog);
            Assert.Equal(new[]
            {
                "Assets/Content/Dialogue/DT_Main_NPC_Test.asset",
                "Assets/Content/Dialogue/DT_Quest_Test_WorldDialogues.asset",
            }, found.ToArray());
        }

        [Fact]
        public void A_catalog_without_internal_ids_yields_nothing_and_broken_json_throws()
        {
            Assert.Empty(CatalogReader.TreeAddresses("{}"));
            Assert.ThrowsAny<System.Text.Json.JsonException>(() => CatalogReader.TreeAddresses("{ kaputt"));
        }
    }
}
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -c Release`
Expected: FAIL beim Bauen (`CatalogReader` fehlt).

- [ ] **Step 3: Leser implementieren** (`mod/DrovaVoice.Core/CatalogReader.cs`)

```csharp
using System;
using System.Collections.Generic;
using System.Text.Json;

namespace DrovaVoice.Core
{
    public static class CatalogReader
    {
        public static IReadOnlyList<string> TreeAddresses(string catalogJson)
        {
            var result = new List<string>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            using var doc = JsonDocument.Parse(catalogJson);
            if (!doc.RootElement.TryGetProperty("m_InternalIds", out var ids) || ids.ValueKind != JsonValueKind.Array) return result;
            foreach (var item in ids.EnumerateArray())
            {
                var path = item.GetString();
                if (path == null || !path.EndsWith(".asset", StringComparison.Ordinal)) continue;
                if (path.StartsWith("Assets/Editor/", StringComparison.Ordinal)) continue;
                int slash = path.LastIndexOf('/');
                if (!path.Substring(slash + 1).StartsWith("DT_", StringComparison.Ordinal)) continue;
                if (seen.Add(path)) result.Add(path);
            }
            return result;
        }
    }
}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -c Release`
Expected: alle grün.

- [ ] **Step 5: Lader in der Mod** (`mod/DrovaVoice/Export/CatalogTreeLoader.cs`)

```csharp
using System;
using System.Collections.Generic;
using Il2CppNodeCanvas.DialogueTrees;
using MelonLoader;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

namespace DrovaVoice.Export
{
    public static class CatalogTreeLoader
    {
        /// <summary>Lädt jeden Baum synchron über seine Adresse. Fehler pro Baum werden gezählt, nie geworfen.</summary>
        public static List<DialogueTree> Load(IReadOnlyList<string> addresses, MelonLogger.Instance log)
        {
            var trees = new List<DialogueTree>();
            int failed = 0;
            for (int i = 0; i < addresses.Count; i++)
            {
                try
                {
                    AsyncOperationHandle<DialogueTree> handle = Addressables.LoadAssetAsync<DialogueTree>(addresses[i]);
                    DialogueTree tree = handle.WaitForCompletion();
                    if (tree != null) trees.Add(tree); else failed++;
                }
                catch (Exception e)
                {
                    failed++;
                    if (failed <= 5) log.Warning($"Laden von {addresses[i]} fehlgeschlagen: {e.GetType().Name}: {e.Message}");
                }
                if ((i + 1) % 200 == 0) log.Msg($"Bäume geladen: {i + 1} von {addresses.Count} (fehlgeschlagen {failed})");
            }
            log.Msg($"Katalog: {trees.Count} Bäume geladen, {failed} fehlgeschlagen, {addresses.Count} Adressen");
            return trees;
        }
    }
}
```

In `mod/DrovaVoice.csproj` bei Bedarf `Unity.Addressables.dll` und `Unity.ResourceManager.dll` ergänzen, falls der Platzhalter aus Task 8 sie nicht abdeckt (beide liegen in `Il2CppAssemblies`). **Risiko:** Il2CppInterop kann `LoadAssetAsync<DialogueTree>` nur aufrufen, wenn das Spiel diese generische Instanz kennt. Schlägt der Aufruf mit einer Ausnahme wie `ExecutionEngineException`/`NotSupportedException` fehl, auf die Basisklasse ausweichen: `Addressables.LoadAssetAsync<UnityEngine.Object>(address)` und das Ergebnis mit `.TryCast<DialogueTree>()` prüfen; die gewählte Variante im Commit-Text vermerken.

- [ ] **Step 6: Zweiten Auslöser einbauen** (`DrovaVoiceMod.cs`)

Neue Felder/Methoden:

```csharp
        private string TriggerAllPath => Path.Combine(ModDir, "export-all.trigger");
```

In `OnUpdate` die letzte Zeile `if (trigger) RunExport();` aus Task 8 durch diesen Block ersetzen (die Prüfung auf `export.trigger` und F9 davor bleibt unverändert):

```csharp
            bool all = false;
            if (_frame % 60 == 0 && File.Exists(TriggerAllPath))
            {
                try { File.Delete(TriggerAllPath); } catch (IOException) { }
                all = true;
            }
            if (all) RunExport(useCatalog: true);
            else if (trigger) RunExport(useCatalog: false);
```

Die Methode `RunExport()` wird zu `RunExport(bool useCatalog)`; darin die Zeile `var manifest = exporter.Export(TreeSource.LoadedTrees());` durch Folgendes ersetzen:

```csharp
                IEnumerable<Il2CppNodeCanvas.DialogueTrees.DialogueTree> trees;
                if (useCatalog)
                {
                    string catalog = Path.Combine(MelonEnvironment.GameRootDirectory, "Drova_Data", "StreamingAssets", "aa", "catalog.json");
                    var addresses = CatalogReader.TreeAddresses(File.ReadAllText(catalog));
                    LoggerInstance.Msg($"Katalog: {addresses.Count} Baum-Adressen");
                    trees = CatalogTreeLoader.Load(addresses, LoggerInstance);
                }
                else trees = TreeSource.LoadedTrees();
                var manifest = exporter.Export(trees);
```
(und `using System.Collections.Generic;` ergänzen).

- [ ] **Step 7: Bauen und im Spiel prüfen**

Run: `dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release`
Expected: Build erfolgreich. Der Nutzer startet das Spiel (Hauptmenü). Dann:
```bash
touch "/d/Games/Steam/steamapps/common/Drova - Forsaken Kin/Mods/DrovaVoice/export-all.trigger"
```
und nach einigen Minuten (das Spiel kann währenddessen stehen) im Log nach `Katalog: … Bäume geladen` und `Export fertig` suchen; dann `export fetch` und `export report`. Expected: Abdeckung >= 98 %. Liegt sie darunter, `coverage_missing.txt` nach Mustern auswerten (Ordner, Baumtypen, Unterbäume mit Generik-Sprechern) und Ursachen ins Ledger schreiben; die Entscheidung über die Notlösung (Spec R1: `.loc`-Dateien mit LLM-Sprecherzuordnung) trifft der Nutzer.

- [ ] **Step 8: Commit**

```bash
git add mod/DrovaVoice.Core/CatalogReader.cs mod/DrovaVoice.Core.Tests/CatalogReaderTests.cs mod/DrovaVoice
git commit -m "Load all dialogue trees from the Addressables catalog" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: NPC- und Variablen-Export, Befunde zu R4

**Files:**
- Create: `mod/DrovaVoice/Export/NpcExporter.cs`, `docs/decisions/2026-10-export-findings.md`
- Modify: `mod/DrovaVoice/DrovaVoiceMod.cs`

**Interfaces:**
- Consumes: Gerüst aus Tasks 8 und 9. Spielklassen (statisch verifiziert): `EntityInfo : ScriptableGuidObject` (`GetLocalizedName()`, `GetLocaKey()`, `HasPortrait()`), `VoiceMap : ScriptableObject` (`GetVoiceID()`, `GetBodyType()`), `ActorGenderSettings : ScriptableObject`; `LocalizationDB.Instance.CurrentLanguage` (`ELanguage`).
- Produces: `npcs.json` mit `[{entity, name, locaKey, hasPortrait}]` und `voices.json` mit `[{asset, voiceId, bodyType}]` unter `Export/<lang>/`; Auslöser `export-npcs.trigger`; ein Befundbericht, ob Geschlecht und Stimm-ID pro NPC erreichbar sind (Risiko R4) und woher die Werte der `$GVAR:`-Variablen kommen.

- [ ] **Step 1: Exporter schreiben** (`mod/DrovaVoice/Export/NpcExporter.cs`)

```csharp
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using Il2CppDrova;
using Il2CppDrova.Sfx.Voices;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Export
{
    public static class NpcExporter
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            WriteIndented = true,
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        };

        public static void Export(string dir, MelonLogger.Instance log)
        {
            Directory.CreateDirectory(dir);
            var npcs = new List<object>();
            foreach (var info in Resources.FindObjectsOfTypeAll<EntityInfo>())
            {
                try
                {
                    npcs.Add(new { entity = info.name, name = info.GetLocalizedName(), locaKey = info.GetLocaKey(), hasPortrait = info.HasPortrait() });
                }
                catch (Exception e) { log.Warning($"EntityInfo {info?.name}: {e.GetType().Name}: {e.Message}"); }
            }
            var voices = new List<object>();
            foreach (var map in Resources.FindObjectsOfTypeAll<VoiceMap>())
            {
                try { voices.Add(new { asset = map.name, voiceId = map.GetVoiceID().ToString(), bodyType = map.GetBodyType().ToString() }); }
                catch (Exception e) { log.Warning($"VoiceMap {map?.name}: {e.GetType().Name}: {e.Message}"); }
            }
            File.WriteAllText(Path.Combine(dir, "npcs.json"), JsonSerializer.Serialize(npcs, Options), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(dir, "voices.json"), JsonSerializer.Serialize(voices, Options), new UTF8Encoding(false));
            log.Msg($"NPC-Export: {npcs.Count} EntityInfo, {voices.Count} VoiceMap -> {dir}");
        }
    }
}
```

- [ ] **Step 2: Auslöser** (`DrovaVoiceMod.cs`)

Feld `private string TriggerNpcsPath => Path.Combine(ModDir, "export-npcs.trigger");`. In `OnUpdate` nach dem `export-all`-Block:

```csharp
            if (_frame % 60 == 30 && File.Exists(TriggerNpcsPath))
            {
                try { File.Delete(TriggerNpcsPath); } catch (IOException) { }
                try { NpcExporter.Export(Path.Combine(ModDir, "Export", _language!.Value), LoggerInstance); }
                catch (Exception e) { LoggerInstance.Error($"NPC-Export fehlgeschlagen: {e}"); }
            }
```

- [ ] **Step 3: Bauen**

Run: `dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release`
Expected: Build erfolgreich (bei fehlenden Membern wie in Task 8 mit dem Typ-Dump korrigieren).

- [ ] **Step 4: Im Spiel prüfen**

Der Nutzer startet das Spiel und **lädt einen Spielstand** (EntityInfo/VoiceMap sind im Hauptmenü evtl. nicht geladen). Dann `export-npcs.trigger` anlegen, `export fetch` ausführen und prüfen:
```bash
python -I -c "import json,pathlib;p=pathlib.Path('data/export/de');n=json.loads((p/'npcs.json').read_text(encoding='utf-8'));v=json.loads((p/'voices.json').read_text(encoding='utf-8'));print(len(n),len(v));print(sum(1 for x in n if x['name']), 'mit Anzeigename')"
```
Expected: zweistellige bis dreistellige Zahlen; die Zahl der NPCs mit Anzeigename notieren.

- [ ] **Step 5: Befunde festhalten** (`docs/decisions/2026-10-export-findings.md`)

Die Datei beantwortet mit Zahlen und Klassennamen (ohne Spieltexte):
1. **R1:** Wie viele Bäume wurden geladen, wie hoch ist die Abdeckung, welche Muster fehlen (Task 9)?
2. **R4:** Ist das Geschlecht pro NPC auslesbar (Quelle: `ActorGenderSettings`, `EntityInfo`, Namenstabelle `NPC_Names/`, Sprecher-Komponenten)? Sind `VoiceMap`-Assets einzelnen NPCs zuordenbar? Wenn nicht: Ersatz Schätzung durch das LLM aus Steckbrief und Porträt (Spec R4).
3. **Variablen:** Woher kommen die Werte der `$GVAR:`-Platzhalter (Namespace `Il2CppDrova.GlobalVarSystem`)? Mit dem Typ-Dump `'GlobalVar(Set|s)?'` die Klassen mit Lesezugriff suchen und festhalten, ob `config`-Werte vor dem Spielstart lesbar sind oder nur aus einem Spielstand. Ergebnis bestimmt, ob `gvars.json` in Plan 3 aus dem Spiel kommt oder aus einer handgepflegten Tabelle.
4. **Anzahl Spielerzeilen** (`category = player`) im Manifest, als Grundlage für die Zahl der Spieler-Stimmsets (M5).

- [ ] **Step 6: Commit**

```bash
git add mod/DrovaVoice docs/decisions/2026-10-export-findings.md
git commit -m "Export entity infos and voice maps and record the findings" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Dokumentation und Abnahme von M1

**Files:**
- Create: `docs/export.md`
- Modify: `docs/setup.md`

**Interfaces:**
- Consumes: alle vorigen Tasks.
- Produces: Anleitung für den Export, Abnahme-Checkliste M1.

- [ ] **Step 1: `docs/export.md` schreiben**

```markdown
# Export aus dem Spiel (M1)

Voraussetzung: Setup nach `docs/setup.md` (MelonLoader, Modding API, Mod gebaut).

1. Spiel starten und im Hauptmenü warten (für `export-npcs` einen Spielstand laden).
2. Auslöser (eine leere Datei anlegen, die Mod löscht sie beim Erkennen):
   - `<Spiel>/Mods/DrovaVoice/export.trigger`: nur die zurzeit geladenen Dialogbäume
   - `<Spiel>/Mods/DrovaVoice/export-all.trigger`: alle Bäume über den Addressables-Katalog (dauert einige Minuten, das Spiel kann währenddessen hängen)
   - `<Spiel>/Mods/DrovaVoice/export-npcs.trigger`: `npcs.json` und `voices.json`
   Alternativ F9 für `export.trigger`, falls die Taste im Spiel funktioniert.
3. Ergebnis: `<Spiel>/Mods/DrovaVoice/Export/<lang>/manifest.json` (+ `npcs.json`, `voices.json`). Die Sprache steht in der MelonLoader-Konfiguration (`ExportLanguage`, Standard `de`); der Text kommt in der aktuellen Spielsprache.
4. Kopieren und prüfen: `drova-voice export fetch`, dann `drova-voice export report` (Exit 0 ab 98 % Abdeckung). Fehlende Einträge stehen in `data/export/<lang>/coverage_missing.txt`.

`data/` ist nicht im Git: Das Manifest enthält Spieltexte.
```

- [ ] **Step 2: `docs/setup.md` um den Verweis ergänzen** (letzter Absatz: `Export: siehe docs/export.md.`)

- [ ] **Step 3: M1-Abnahme prüfen und festhalten**

Run:
```bash
cd generator && .venv/Scripts/python -m pytest -q && cd .. && dotnet test mod/DrovaVoice.Core.Tests -c Release
cd generator && .venv/Scripts/drova-voice export report
```
Expected: alle Tests grün; Abdeckung >= 98 %. Die Zahlen (Bäume, Zeilen, Abdeckung, Anteil Spielerzeilen) stehen im Ledger und in `docs/decisions/2026-10-export-findings.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/export.md docs/setup.md
git commit -m "Document the export workflow" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Nach Plan 2

Mit den Ergebnissen aus Teil A (Durchsatz, Limits, Kosten) und Teil B (Manifest, R1/R4, Spielerzeilen) wird **Plan 3** geschrieben: Generator-Schritte `extract`, `cast`, `emote`, `synth` (Fish, parallel, mit Cache und Plausibilitätsprüfung), `encode`, `install` und die Wiedergabe in der Mod für **einen NPC (Adela)** (M3). Dort gehören auch die Spec-Lücken hinein, die der Plan-1-Review nannte: Modellversion im Handshake, Aufteilung langer Texte, `ref.txt` im Stimmen-Pool und die Zuordnung der acht Fish-Stimmen zu den Figuren.
