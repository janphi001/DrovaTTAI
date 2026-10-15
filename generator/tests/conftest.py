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


# --- Fixture für die Pipeline-Schritte (Plan 3) --------------------------------------------------------------
import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

_LOC_TEXT = (
    "Plh_1 { *seufzt* Der Weg nach Norden ist weit. }\n"
    "Plh_2 { Wohin soll ich dich führen? }\n"
    "Plh_3 { Zum Brunnen, bitte. }\n"
    "Plh_4 { Hallo $GVAR:EVars_Player.Name$! }\n"
    "Plh_5 { *grinst* }\n"
)


def _manifest_line(key, node_id, actor, category, node_type="statement", choice_index=None):
    tree, path = "DT_Test_NPC_Mira", "Dialog/NPC_Mira"
    line_id = f"{tree}|{path}|{key}" + (f"|c{choice_index}" if choice_index is not None else "")
    row = {"id": line_id, "tree": tree, "nodeId": node_id, "nodeType": node_type, "actorName": actor,
           "category": category, "generic": False, "locaPath": path, "locaKey": key, "text": "x", "gvars": []}
    if choice_index is not None:
        row["choiceIndex"] = choice_index
    return row


@pytest.fixture
def pipeline_repo(tmp_path):
    """Kleines Repo mit erfundenem Text: Spiel-.loc, Manifest, Stimmentabelle und casting.yaml."""
    repo = tmp_path / "repo"
    gen = repo / "generator"
    gen.mkdir(parents=True)
    game = tmp_path / "game"
    loc = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    loc.mkdir(parents=True)
    (loc / "NPC_Mira_de.loc").write_text(_LOC_TEXT, encoding="utf-8")
    export = repo / "data" / "export" / "de"
    export.mkdir(parents=True)
    manifest = {"version": 1, "language": "de", "lines": [
        _manifest_line("Plh_1", 1, "Mira", "dialog"),
        _manifest_line("Plh_2", 2, "Mira", "dialog"),
        _manifest_line("Plh_3", 3, "Player", "player"),                  # Spieler-Aussage: wird gesprochen (default_player)
        _manifest_line("Plh_4", 4, "Mira", "dialog"),
        _manifest_line("Plh_5", 5, "Mira", "dialog"),
        _manifest_line("Plh_6", 6, "Player", "player", "choice", 0),     # Auswahloption: wird übersprungen (player_choice)
    ]}
    (export / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    casting = repo / "casting"
    casting.mkdir()
    (casting / "fish_voices.yaml").write_text(
        "voices:\n"
        "  lena: {id: \"3937b44b604249f18b94913daef94043\", label: Lena, gender: f}\n"
        "  leon: {id: \"7b7c88bf825a4ab3bca27d55c26ddf16\", label: Leon, gender: m}\n", encoding="utf-8")
    (casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers:\n  mira: {voice: lena}\n", encoding="utf-8")
    cfg = gen / "config.yaml"
    cfg.write_text(f"game_dir: '{game.as_posix()}'\nlanguage: de\n", encoding="utf-8")
    return SimpleNamespace(repo=repo, game=game, cfg=cfg, data=repo / "data", casting=casting,
                           install_dir=game / "Mods" / "DrovaVoice" / "Audio" / "de")
