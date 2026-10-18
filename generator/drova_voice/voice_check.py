"""Genutzte Fish-Stimmen gegen die API prüfen. Der HTTP-Aufruf bleibt im Fish-Worker."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.casting import Casting
from drova_voice.engines.client import EngineError, worker_command
from drova_voice.fish_voices import Catalog

UNUSABLE = frozenset({"missing", "taken_down", "unavailable"})
SKIPPED = "Stimmenprüfung übersprungen: FISH_API_KEY ist nicht gesetzt."


@dataclass(frozen=True)
class VoiceUse:
    key: str
    voice_id: str


def api_key(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    return source.get("FISH_API_KEY", "").strip()


def used_voices(catalog: Catalog, casting: Casting) -> list[VoiceUse]:
    """Stimme oder Variante, die die Besetzung wirklich verwendet, mit der Fish-ID der Basis."""
    keys = set(casting.speakers.values()) | set(casting.pools.values())
    if casting.default_player:
        keys.add(casting.default_player)
    table = catalog.synth_table()
    return [VoiceUse(key, table[key].id) for key in sorted(keys)]


def substitute(catalog: Catalog, key: str, bad_ids: set[str]) -> str | None:
    """Erster Fallback, dessen Fish-ID nicht in bad_ids liegt. None, wenn keiner trägt."""
    table = catalog.synth_table()
    seen: set[str] = set()
    current = key
    while current not in seen:
        seen.add(current)
        nxt = catalog.fallbacks.get(current)
        if nxt is None and current in catalog.variants:
            nxt = catalog.fallbacks.get(catalog.variants[current].base)
        if nxt is None or nxt not in table:
            return None
        if table[nxt].id not in bad_ids:
            return nxt
        current = nxt
    return None


def summarize(uses: Sequence[VoiceUse], statuses: Mapping[str, dict], catalog: Catalog) -> tuple[list[str], int]:
    """Zeilen und Exit-Code. Fehlende Stimme mit Fallback ist gedeckt; ohne Fallback scheitert die Prüfung."""
    by_id = {row.voice_id: statuses.get(row.voice_id, {"status": "error", "detail": "keine Antwort"}) for row in uses}
    # Auch Fallbacks, die selbst fehlen oder deren Prüfung scheiterte, tragen nicht.
    bad_ids = {
        vid for vid, info in {**statuses, **by_id}.items()
        if info.get("status") in UNUSABLE or info.get("status") not in {"ok", "retiring"}
    }
    lines: list[str] = []
    failed = 0
    errors = 0
    retiring = 0
    covered = 0
    ok = 0
    for row in uses:
        info = by_id[row.voice_id]
        status = str(info.get("status") or "error")
        if status == "ok":
            ok += 1
            continue
        if status == "retiring":
            retiring += 1
            when = info.get("retire_at") or "ohne Datum"
            lines.append(f"LÄUFT AB {row.key} ({row.voice_id}): wirksam {when}")
            continue
        if status in UNUSABLE:
            target = substitute(catalog, row.key, bad_ids)
            if target is not None:
                covered += 1
                lines.append(f"ERSATZ {row.key} ({row.voice_id}): {status}, Fallback {target}")
            else:
                failed += 1
                lines.append(f"FEHLT {row.key} ({row.voice_id}): {status}, kein Fallback")
            continue
        errors += 1
        detail = info.get("detail") or status
        lines.append(f"FEHLER {row.key} ({row.voice_id}): {detail}")
    head = (
        f"Stimmenprüfung: {ok} in Ordnung, {covered} mit Fallback, {failed} ohne Fallback, "
        f"{retiring} laufen ab, {errors} Fehler."
    )
    code = 2 if errors else (1 if failed else 0)
    return [head, *lines], code


def query_voices(workers_dir: Path, ids: Sequence[str], env: Mapping[str, str] | None = None) -> list[dict]:
    """Fish-Worker im Prüfmodus. Der Schlüssel bleibt in der Umgebung und steht in keiner Argumentliste."""
    cmd = worker_command(Path(workers_dir), "fish")
    proc_env = dict(os.environ if env is None else env)
    proc_env["FISH_VOICE_CHECK"] = "1"
    proc_env["PYTHONIOENCODING"] = "utf-8"
    proc_env["PYTHONUTF8"] = "1"
    try:
        completed = subprocess.run(
            cmd, input=json.dumps({"ids": list(ids)}), text=True, capture_output=True,
            env=proc_env, timeout=300, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise EngineError(f"Stimmenprüfung nicht gelaufen: {type(e).__name__}: {e}") from e
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or f"Exit {completed.returncode}").strip()
        raise EngineError(detail[:500])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as e:
        raise EngineError(f"Stimmenprüfung lieferte kein JSON: {e}") from e
    voices = payload.get("voices") if isinstance(payload, dict) else None
    if not isinstance(voices, list):
        raise EngineError("Stimmenprüfung lieferte keine Liste")
    return voices
