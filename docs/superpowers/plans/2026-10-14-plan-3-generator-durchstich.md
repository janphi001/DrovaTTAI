# Generator-Durchstich (Adela) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aus dem Export (`manifest-loaded.json`) deutsche Sprachdateien für die Dialoge eines NPC erzeugen (extract → cast → emote → synth → encode → install), mit `index.json` im Mod-Ordner, Bericht und Hörseite; erster echter Lauf für Adela.

**Architecture:** Jeder Schritt ist ein Unterbefehl von `drova-voice` in einem eigenen Modul (`lines`, `casting`, `emote`, `synth`, `encode`, `install`, `report`, `preview`); `pipeline.py` verdrahtet sie mit der CLI. Zwischenergebnisse liegen als JSONL unter `data/` (nicht im Git), alle Schritte sind wiederaufnehmbar. `--npc NAME` wählt alle Bäume, in denen der NPC spricht (inklusive der Spieler-Auswahloptionen derselben Bäume).

**Tech Stack:** Python 3.11, pytest, pyyaml, num2words (keine neuen Abhängigkeiten), ffmpeg/ffprobe (vorhanden), Fish-Worker (`generator/workers/fish`), Fake-Worker für Tests.

**Spec:** `docs/superpowers/specs/2026-10-10-drova-voice-design.md` (§4, §6, §7, §15). Die C#-Wiedergabe (§9) ist **nicht** Teil dieses Plans, sondern Plan 4; die Datei- und Indexform steht hier in `docs/audio-format.md` (Task 6) und ist der Vertrag dafür.

## Global Constraints

- Antworten, Kommentare und Meldungen auf Deutsch; Bezeichner im Code auf Englisch (wie im bestehenden Code).
- **Keine echten Drova-Texte im Git**: Tests und Dokumente verwenden erfundenen Text. `data/`, `out/`, `cache/`, `voices/` sind git-ignoriert.
- Keine Spieltexte an Dienste senden ohne ausdrückliches Ja des Nutzers in der Hauptsitzung (gilt für Task 9: Fish und Haiku-Subagent).
- Keine Downloads/Installationen ohne vorherige Rückfrage; alles auf Laufwerk D:.
- Fish-Schlüssel nur als Umgebungsvariable `FISH_API_KEY`, nie in Dateien, Befehlen im Repo oder Commits.
- Zeilen-IDs ausschließlich über `drova_voice.ids` bilden (`statement_id`, `choice_id`, `with_variant`, `audio_filename`).
- Fish-Messwerte (`docs/decisions/2026-10-fish-throughput.md`): 8 parallele Anfragen als Standard, gemessen rund 17 Zeichen Sprechtext pro Sekunde Audio.
- Commit-Nachrichten sind englisch, Imperativ, ohne Claude-Trailer.
- Arbeitsverzeichnis für Python-Befehle: `generator/`; Aufruf über `.venv/Scripts/python.exe` bzw. `.venv/Scripts/drova-voice`.

## Review Focus

- Zeile mit `$GVAR:` im Text (233 mit Spielername, 275 weitere): darf weder mit leerem Platzhalter noch mit „Arden“ gesprochen werden; sie wird übersprungen und im Bericht als `gvar` gezählt (Namensvarianten kommen später).
- Zeile ohne sprechbaren Inhalt (`*seufzt*`, `…`): kein Aufruf an Fish, Grund `unspeakable` im Bericht.
- Abbruch mitten im `synth`-Lauf (Strg+C, toter Worker, halbe Datei): Wiederaufnahme ohne doppelte Arbeit, keine halbfertigen WAVs im Cache, eine abgeschnittene letzte Zeile in `results.jsonl` bricht das Lesen nicht.
- Manifest-ID passt nicht zu `Baum|Pfad|Schlüssel`, doppelte IDs: keine falsche Zuordnung, nie in `index.json`.
- Sprecher ohne Stimme oder Stimmenschlüssel, der nicht in `fish_voices.yaml` steht: klare Fehlermeldung statt Lauf mit falscher Stimme.
- Zweiter `install` für einen anderen NPC darf die Einträge des ersten nicht löschen; Umlaute in IDs bleiben lesbar (`ensure_ascii=False`).
- ffmpeg fehlt oder kann kein Vorbis: verständlicher Fehler vor dem ersten Datei-Lauf.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `generator/drova_voice/config.py` (ändern) | Pfade `cache_dir`, `casting_dir`, `install_dir` |
| `generator/drova_voice/jsonl.py` (ändern) | `append_jsonl`, `read_jsonl_lenient`, `latest_by_id` |
| `generator/drova_voice/lines.py` (neu) | `Line`, `.loc`-Texte laden, Manifest → Zeilen mit Sprechtext, `select_npc` |
| `generator/drova_voice/casting.py` (neu) | `casting.yaml` laden, Stimme je Zeile, Prüfbericht |
| `generator/drova_voice/emote.py` (neu) | Emotionen aus Regieanweisungen, Mischen mit LLM/manuellen Zeilen, Lesen/Schreiben |
| `generator/drova_voice/synth.py` (neu) | Aufträge, Cache-Schlüssel, Plausibilität, paralleler Lauf |
| `generator/drova_voice/encode.py` (neu) | ffmpeg-Kette, Dateipfad je Zeile, Lauf |
| `generator/drova_voice/install.py` (neu) | Kopieren in den Mod-Ordner, `index.json` mit Zusammenführen |
| `generator/drova_voice/report.py` (neu) | Statusbericht je Kategorie |
| `generator/drova_voice/preview.py` (neu) | Hörseite für einen NPC |
| `generator/drova_voice/pipeline.py` (neu) | Unterbefehle verdrahten (`add_parsers`, `HANDLERS`) |
| `generator/drova_voice/cli.py` (ändern) | `pipeline.add_parsers` einhängen, Dispatch |
| `casting/casting.yaml`, `casting/lexicon.yaml`, `casting/emotions.jsonl` (neu) | Sprecher → Stimme, Aussprache, Emotionen (nur IDs/Labels) |
| `docs/audio-format.md`, `docs/generator.md` (neu) | Vertrag für die Mod, Bedienung |
| `generator/tests/test_*.py` (neu) | je Modul; `conftest.py` bekommt das Fixture `pipeline_repo` |

---

### Task 1: Config-Pfade, JSONL-Helfer und `extract`

**Files:**
- Modify: `generator/drova_voice/config.py`, `generator/drova_voice/jsonl.py`, `generator/drova_voice/cli.py`, `generator/tests/conftest.py`
- Create: `generator/drova_voice/lines.py`, `generator/drova_voice/pipeline.py`, `casting/lexicon.yaml`
- Test: `generator/tests/test_config_paths.py`, `generator/tests/test_jsonl_helpers.py`, `generator/tests/test_lines.py`, `generator/tests/test_pipeline_extract.py`

**Interfaces:**
- Consumes: `ids.statement_id/choice_id/normalize_loca_path`, `loc.parse_loc`, `speech_text.build_speech_text`, `export_report.loca_path_of`, `jsonl.write_jsonl/read_jsonl`.
- Produces:
  - `Config.cache_dir`, `Config.casting_dir`, `Config.install_dir` (`<game_dir>/Mods/DrovaVoice/Audio/<language>`).
  - `jsonl.append_jsonl(path: Path, row: dict) -> None`, `jsonl.read_jsonl_lenient(path: Path) -> list[dict]` (fehlende Datei → `[]`, nicht lesbare Zeilen werden übersprungen), `jsonl.latest_by_id(rows: Iterable[dict]) -> dict[str, dict]` (letzte Zeile je `id` gewinnt).
  - `lines.Line` (frozen dataclass: `id, tree, loca_path, loca_key, node_type, choice_index, actor, category, generic, raw, speech, stage, skip`; `to_dict()`, `from_dict()`), Konstanten `SKIP_GVAR="gvar"`, `SKIP_UNSPEAKABLE="unspeakable"`, `SKIP_ID_MISMATCH="id_mismatch"`.
  - `lines.load_loc_texts(loc_dir: Path, language: str) -> dict[tuple[str, str], str]`, `lines.build_lines(manifest: dict, loc_texts: Mapping, lexicon: Mapping | None = None) -> list[Line]`, `lines.select_npc(lines: Sequence[Line], npc: str) -> list[Line]`, `lines.write_lines(path, lines)`, `lines.read_lines(path) -> list[Line]`, `lines.load_lexicon(path) -> dict[str, str]`.
  - `pipeline.add_parsers(sub)`, `pipeline.HANDLERS: dict[str, Callable[[Config, Namespace], int]]`, Hilfen `pipeline._selected(cfg, args)`, `pipeline._fail(msg)`.
  - Fixture `pipeline_repo` (siehe Step 1).

- [ ] **Step 1: Fixture `pipeline_repo` an `conftest.py` anhängen**

Run (Bash, im Repo-Stamm):
```bash
cat >> generator/tests/conftest.py <<'EOF'


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
        _manifest_line("Plh_3", 3, "Player", "player", "choice", 0),
        _manifest_line("Plh_4", 4, "Mira", "dialog"),
        _manifest_line("Plh_5", 5, "Mira", "dialog"),
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
EOF
```
Expected: kein Fehler. (Die Fixture-Texte sind erfunden. `pytest` ist in `conftest.py` bereits importiert.)

- [ ] **Step 2: Failing Tests schreiben**

`generator/tests/test_config_paths.py`:
```python
from pathlib import Path

from drova_voice.config import load_config


def test_new_paths(tmp_path):
    (tmp_path / "generator").mkdir()
    cfg_file = tmp_path / "generator" / "config.yaml"
    cfg_file.write_text("game_dir: 'D:/Spiel'\nlanguage: de\n", encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.cache_dir == tmp_path.resolve() / "cache"
    assert cfg.casting_dir == tmp_path.resolve() / "casting"
    assert cfg.install_dir == Path("D:/Spiel") / "Mods" / "DrovaVoice" / "Audio" / "de"
```

`generator/tests/test_jsonl_helpers.py`:
```python
from drova_voice.jsonl import append_jsonl, latest_by_id, read_jsonl_lenient


def test_append_and_read(tmp_path):
    path = tmp_path / "sub" / "r.jsonl"
    append_jsonl(path, {"id": "a", "v": 1})
    append_jsonl(path, {"id": "b", "v": "Bär"})
    assert read_jsonl_lenient(path) == [{"id": "a", "v": 1}, {"id": "b", "v": "Bär"}]


def test_lenient_skips_truncated_last_line_and_missing_file(tmp_path):
    assert read_jsonl_lenient(tmp_path / "gibt-es-nicht.jsonl") == []
    path = tmp_path / "r.jsonl"
    path.write_text('{"id": "a"}\n{"id": "b", "v": [1, 2', encoding="utf-8")  # Abbruch beim Schreiben
    assert read_jsonl_lenient(path) == [{"id": "a"}]


def test_latest_by_id_last_row_wins():
    rows = [{"id": "a", "n": 1}, {"id": "b", "n": 1}, {"id": "a", "n": 2}]
    assert latest_by_id(rows) == {"a": {"id": "a", "n": 2}, "b": {"id": "b", "n": 1}}
```

`generator/tests/test_lines.py`:
```python
from drova_voice.ids import choice_id, statement_id
from drova_voice.lines import (SKIP_GVAR, SKIP_ID_MISMATCH, SKIP_UNSPEAKABLE, Line, build_lines, load_lexicon,
                               load_loc_texts, read_lines, select_npc, write_lines)

TREE, PATH = "DT_Test_NPC_Mira", "Dialog/NPC_Mira"


def mline(key, **over):
    d = {"id": statement_id(TREE, PATH, key), "tree": TREE, "nodeId": 1, "nodeType": "statement",
         "actorName": "Mira", "category": "dialog", "generic": False, "locaPath": PATH, "locaKey": key,
         "text": "Text aus dem Manifest.", "gvars": []}
    d.update(over)
    return d


def manifest(*lines):
    return {"version": 1, "language": "de", "lines": list(lines)}


def test_loc_text_wins_over_manifest_text():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Text aus der Loc."})
    assert line.raw == "Text aus der Loc." and line.speech == "Text aus der Loc." and line.skip is None


def test_falls_back_to_manifest_text_without_loc_entry():
    (line,) = build_lines(manifest(mline("Plh_1")), {})
    assert line.speech == "Text aus dem Manifest."


def test_stage_directions_are_split_off():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "*seufzt* Das ist lange her."})
    assert line.speech == "Das ist lange her."
    assert line.stage[0]["text"] == "seufzt" and line.stage[0]["pos"] == 0


def test_lexicon_is_applied():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Willkommen in Zorgrad."}, {"Zorgrad": "Sorgrad"})
    assert line.speech == "Willkommen in Sorgrad."


def test_gvar_lines_are_skipped_not_spoken():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Hallo $GVAR:EVars_Player.Name$!"})
    assert line.skip == SKIP_GVAR and line.speech == ""


def test_unspeakable_lines_are_skipped():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_2")), {(PATH, "Plh_1"): "*seufzt*", (PATH, "Plh_2"): "…"})
    assert [l.skip for l in lines] == [SKIP_UNSPEAKABLE, SKIP_UNSPEAKABLE]


def test_id_mismatch_is_skipped():
    (line,) = build_lines(manifest(mline("Plh_1", id="Falsch|Pfad|Plh_1")), {})
    assert line.skip == SKIP_ID_MISMATCH and line.speech == ""


def test_choice_line_id_uses_the_index():
    row = mline("Plh_3", nodeType="choice", choiceIndex=2, actorName="Player", category="player",
                id=choice_id(TREE, PATH, "Plh_3", 2))
    (line,) = build_lines(manifest(row), {(PATH, "Plh_3"): "Zum Brunnen, bitte."})
    assert line.skip is None and line.choice_index == 2 and line.id.endswith("|c2")


def test_duplicate_ids_keep_the_first():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_1", text="Zweite Fassung.")), {})
    assert len(lines) == 1 and lines[0].speech == "Text aus dem Manifest."


def test_select_npc_keeps_whole_trees():
    other = mline("Plh_9", tree="DT_Anders", id=statement_id("DT_Anders", PATH, "Plh_9"), actorName="Bart")
    player = mline("Plh_3", nodeType="choice", choiceIndex=0, actorName="Player", category="player",
                   id=choice_id(TREE, PATH, "Plh_3", 0))
    lines = build_lines(manifest(mline("Plh_1"), player, other), {})
    assert [l.actor for l in select_npc(lines, "mira")] == ["Mira", "Player"]
    assert select_npc(lines, "Nobody") == []


def test_roundtrip_and_loc_loading(tmp_path):
    loc_dir = tmp_path / "loc"
    (loc_dir / "Dialog").mkdir(parents=True)
    (loc_dir / "Dialog" / "NPC_Mira_de.loc").write_text("Plh_1 { Hallo }\n", encoding="utf-8")
    texts = load_loc_texts(loc_dir, "de")
    assert texts == {("Dialog/NPC_Mira", "Plh_1"): "Hallo"}
    lines = build_lines(manifest(mline("Plh_1")), texts)
    write_lines(tmp_path / "lines.jsonl", lines)
    assert read_lines(tmp_path / "lines.jsonl") == lines
    assert isinstance(lines[0], Line)


def test_load_lexicon_missing_or_empty(tmp_path):
    assert load_lexicon(tmp_path / "nix.yaml") == {}
    (tmp_path / "lex.yaml").write_text("# nur Kommentar\n", encoding="utf-8")
    assert load_lexicon(tmp_path / "lex.yaml") == {}
    (tmp_path / "lex.yaml").write_text("Zorgrad: Sorgrad\n", encoding="utf-8")
    assert load_lexicon(tmp_path / "lex.yaml") == {"Zorgrad": "Sorgrad"}
```

`generator/tests/test_pipeline_extract.py`:
```python
from drova_voice.cli import main
from drova_voice.lines import read_lines


def test_extract_writes_lines_and_reports_skips(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    assert [l.skip for l in lines] == [None, None, None, "gvar", "unspeakable"]
    assert lines[0].speech == "Der Weg nach Norden ist weit." and lines[0].stage[0]["text"] == "seufzt"
    out = capsys.readouterr().out
    assert "5 Zeilen" in out and "gvar: 1" in out and "unspeakable: 1" in out


def test_extract_without_manifest_fails_clearly(pipeline_repo, capsys):
    (pipeline_repo.data / "export" / "de" / "manifest.json").unlink()
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    assert "Manifest nicht gefunden" in capsys.readouterr().err
```

- [ ] **Step 3: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_config_paths.py tests/test_jsonl_helpers.py tests/test_lines.py tests/test_pipeline_extract.py -q`
Expected: FAIL (`ImportError`/`AttributeError`: neue Module und Eigenschaften fehlen).

- [ ] **Step 4: Config und JSONL erweitern**

`generator/drova_voice/config.py`: nach der Eigenschaft `workers_dir` einfügen:
```python
    @property
    def cache_dir(self) -> Path:
        return self.repo_root / "cache"

    @property
    def casting_dir(self) -> Path:
        return self.repo_root / "casting"

    @property
    def install_dir(self) -> Path:
        return self.game_dir / "Mods" / "DrovaVoice" / "Audio" / self.language
```

`generator/drova_voice/jsonl.py`: am Dateiende anhängen:
```python
def append_jsonl(path: Path, row: dict) -> None:
    # Anhängen statt neu schreiben: Ein Abbruch kostet höchstens die letzte (halbe) Zeile.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl_lenient(path: Path) -> list[dict]:
    """Wie read_jsonl, aber: fehlende Datei -> [], nicht lesbare Zeilen (z. B. abgebrochenes Schreiben) werden übersprungen."""
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def latest_by_id(rows: Iterable[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows if "id" in row}
```

- [ ] **Step 5: `lines.py` schreiben**

`generator/drova_voice/lines.py`:
```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from drova_voice.export_report import loca_path_of
from drova_voice.ids import choice_id, normalize_loca_path, statement_id
from drova_voice.jsonl import read_jsonl, write_jsonl
from drova_voice.loc import parse_loc
from drova_voice.speech_text import build_speech_text

SKIP_GVAR = "gvar"
SKIP_UNSPEAKABLE = "unspeakable"
SKIP_ID_MISMATCH = "id_mismatch"


@dataclass(frozen=True)
class Line:
    id: str
    tree: str
    loca_path: str
    loca_key: str
    node_type: str
    choice_index: int | None
    actor: str
    category: str
    generic: bool
    raw: str  # Text der .loc (oder des Manifests), noch mit Regieanweisungen und Platzhaltern
    speech: str  # Sprechtext, leer bei übersprungenen Zeilen
    stage: tuple[dict, ...] = ()  # [{"text": "seufzt", "pos": 0}], pos = Zeichenindex im Sprechtext
    skip: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Line":
        return cls(**{**d, "stage": tuple(d.get("stage", ()))})


def load_loc_texts(loc_dir: Path, language: str) -> dict[tuple[str, str], str]:
    texts: dict[tuple[str, str], str] = {}
    loc_dir = Path(loc_dir)
    for file in sorted(loc_dir.rglob("*.loc")):
        path = loca_path_of(file, loc_dir, language)
        for entry in parse_loc(file.read_text(encoding="utf-8-sig", errors="replace")).entries:
            texts[(path, entry.key)] = entry.text
    return texts


def load_lexicon(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Lexikon muss aus 'Wort: Aussprache'-Zeilen bestehen")
    return {str(k): str(v) for k, v in raw.items()}


def _expected_id(row: Mapping) -> str:
    if row.get("nodeType") == "choice":
        return choice_id(row["tree"], row["locaPath"], row["locaKey"], int(row["choiceIndex"]))
    return statement_id(row["tree"], row["locaPath"], row["locaKey"])


def build_lines(manifest: Mapping, loc_texts: Mapping[tuple[str, str], str],
                lexicon: Mapping[str, str] | None = None) -> list[Line]:
    seen: set[str] = set()
    out: list[Line] = []
    for row in manifest.get("lines", []):
        line_id = row["id"]
        if line_id in seen:  # gleiche Bäume können mehrfach im Speicher liegen
            continue
        seen.add(line_id)
        path = normalize_loca_path(row["locaPath"])
        raw = loc_texts.get((path, row["locaKey"]), row.get("text") or "")
        try:
            id_ok = _expected_id(row) == line_id
        except (KeyError, TypeError, ValueError):
            id_ok = False
        speech, stage, skip = "", (), None
        if not id_ok:
            skip = SKIP_ID_MISMATCH
        elif "$GVAR:" in raw:
            skip = SKIP_GVAR
        else:
            st = build_speech_text(raw, None, lexicon)
            if st.is_speakable:
                speech, stage = st.text, tuple({"text": s.text, "pos": s.pos} for s in st.stage)
            else:
                skip = SKIP_UNSPEAKABLE
        out.append(Line(
            id=line_id, tree=row["tree"], loca_path=path, loca_key=row["locaKey"], node_type=row["nodeType"],
            choice_index=row.get("choiceIndex"), actor=row.get("actorName") or "", category=row.get("category") or "dialog",
            generic=bool(row.get("generic")), raw=raw, speech=speech, stage=stage, skip=skip,
        ))
    return out


def select_npc(lines: Sequence[Line], npc: str) -> list[Line]:
    """Alle Zeilen der Bäume, in denen der NPC spricht (inklusive Spieler-Auswahloptionen derselben Bäume)."""
    wanted = npc.lower()
    trees = {l.tree for l in lines if l.actor.lower() == wanted}
    return [l for l in lines if l.tree in trees]


def write_lines(path: Path, lines: Sequence[Line]) -> None:
    write_jsonl(path, (l.to_dict() for l in lines))


def read_lines(path: Path) -> list[Line]:
    return [Line.from_dict(d) for d in read_jsonl(path)]
```

`casting/lexicon.yaml`:
```yaml
# Aussprache-Lexikon: Wort im Text -> so soll es gesprochen werden (Fantasienamen, Eigennamen).
# Format: `Wort: Aussprache`. Wird beim extract-Schritt auf den Sprechtext angewendet.
# Bewusst leer: Einträge kommen aus Hörtests (nur Wörter, keine Sätze aus dem Spiel).
```

- [ ] **Step 6: `pipeline.py` anlegen und in `cli.py` einhängen**

`generator/drova_voice/pipeline.py`:
```python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

from drova_voice.config import Config
from drova_voice.lines import (Line, build_lines, load_lexicon, load_loc_texts, read_lines, select_npc, write_lines)

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"


def _fail(message: str) -> int:
    print(f"FEHLER: {message}", file=sys.stderr)
    return 2


def lines_path(cfg: Config) -> Path:
    return cfg.data_dir / "lines.jsonl"


def _selected(cfg: Config, args: argparse.Namespace) -> list[Line] | None:
    """Zeilen aus data/lines.jsonl, bei --npc gefiltert; None (mit Meldung), wenn extract noch nicht lief."""
    path = lines_path(cfg)
    if not path.is_file():
        _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
        return None
    lines = read_lines(path)
    npc = getattr(args, "npc", None)
    if npc:
        lines = select_npc(lines, npc)
        if not lines:
            _fail(f"Keine Zeilen für NPC '{npc}' gefunden")
            return None
    return lines


def _extract(cfg: Config, args: argparse.Namespace) -> int:
    manifest_path = args.manifest or (cfg.data_dir / "export" / cfg.language / "manifest.json")
    if not Path(manifest_path).is_file():
        return _fail(f"Manifest nicht gefunden: {manifest_path} (Export im Spiel auslösen, siehe docs/export.md)")
    if not cfg.loc_dir.is_dir():
        return _fail(f"Lokalisierungsordner nicht gefunden: {cfg.loc_dir} (game_dir in config.yaml prüfen)")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    lexicon = load_lexicon(cfg.casting_dir / "lexicon.yaml")
    lines = build_lines(manifest, load_loc_texts(cfg.loc_dir, cfg.language), lexicon)
    write_lines(lines_path(cfg), lines)
    skips = Counter(l.skip for l in lines if l.skip)
    detail = ", ".join(f"{reason}: {n}" for reason, n in sorted(skips.items())) or "keine"
    print(f"{len(lines)} Zeilen -> {lines_path(cfg)}; übersprungen: {detail}")
    return 0


HANDLERS: dict[str, Callable[[Config, argparse.Namespace], int]] = {
    "extract": _extract,
}


def add_parsers(sub) -> None:
    ex = sub.add_parser("extract", help="Manifest + .loc -> data/lines.jsonl (Sprechtext)")
    ex.add_argument("--manifest", type=Path, help="Standard: data/export/<Sprache>/manifest.json")
```

`generator/drova_voice/cli.py`: (a) Import ergänzen: `from drova_voice import pipeline` (neben den anderen `from drova_voice...`-Importen); (b) in `_parse`, direkt vor `return p.parse_args(argv)`: `pipeline.add_parsers(sub)`; (c) in `_run` direkt nach dem `bake_data = ...`-Block (vor `if args.cmd == "smoke":`):
```python
    handler = pipeline.HANDLERS.get(args.cmd)
    if handler is not None:
        return handler(cfg, args)
```

- [ ] **Step 7: Tests laufen lassen (müssen grün sein)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle Tests grün (vorher 303, jetzt plus die neuen).

- [ ] **Step 8: Commit**

```bash
git add generator casting/lexicon.yaml
git commit -m "Add the extract step: speech text per line from the manifest and .loc"
```

---

### Task 2: Casting (Sprecher → Stimme) und `cast --check`

**Files:**
- Create: `generator/drova_voice/casting.py`, `casting/casting.yaml`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_casting.py`, `generator/tests/test_pipeline_cast.py`

**Interfaces:**
- Consumes: `fish_voices.load_fish_voices(path) -> dict[str, FishVoice]`, `lines.Line`, `pipeline._selected`.
- Produces: `casting.Casting` (frozen dataclass: `default_player: str`, `speakers: dict[str, str]`; Methode `voice_for(line: Line) -> str | None`: Spielerzeilen → `default_player`, sonst `speakers.get(actor.lower())`), `casting.load_casting(path: Path, voices: Mapping[str, FishVoice]) -> Casting`, `casting.cast_report(lines, casting) -> CastReport` (`missing: dict[str, int]` Sprecher → Zeilenzahl, `usage: dict[str, int]` Stimme → Zeilenzahl; übersprungene Zeilen zählen nicht), `pipeline._cast`.

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_casting.py`:
```python
import pytest

from drova_voice.casting import cast_report, load_casting
from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line

VOICES = {
    "lena": FishVoice("lena", "a" * 32, "Lena", "f", "de"),
    "leon": FishVoice("leon", "b" * 32, "Leon", "m", "de"),
}


def line(actor, category="dialog", skip=None, key="Plh_1"):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw="x", speech="x", stage=(), skip=skip)


def write(tmp_path, text):
    path = tmp_path / "casting.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_voice_for_speaker_and_player(tmp_path):
    c = load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  Mira: {voice: lena}\n"), VOICES)
    assert c.voice_for(line("Mira")) == "lena"
    assert c.voice_for(line("MIRA")) == "lena"  # Groß-/Kleinschreibung egal
    assert c.voice_for(line("Player", category="player")) == "leon"
    assert c.voice_for(line("Fremder")) is None


def test_unknown_voice_is_a_clear_error(tmp_path):
    path = write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: gibtsnicht}\n")
    with pytest.raises(ValueError, match="gibtsnicht.*mira"):
        load_casting(path, VOICES)


def test_unknown_default_player_and_missing_default(tmp_path):
    with pytest.raises(ValueError, match="default_player"):
        load_casting(write(tmp_path, "default_player: nix\nspeakers: {}\n"), VOICES)
    with pytest.raises(ValueError, match="default_player"):
        load_casting(write(tmp_path, "speakers: {}\n"), VOICES)


def test_duplicate_speaker_after_lowercasing(tmp_path):
    path = write(tmp_path, "default_player: leon\nspeakers:\n  Mira: {voice: lena}\n  mira: {voice: leon}\n")
    with pytest.raises(ValueError, match="doppelt"):
        load_casting(path, VOICES)


def test_cast_report_counts_missing_and_usage(tmp_path):
    c = load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: lena}\n"), VOICES)
    lines = [line("Mira", key="Plh_1"), line("Mira", key="Plh_2"), line("Fremder", key="Plh_3"),
             line("Player", "player", key="Plh_4"), line("Fremder", skip="gvar", key="Plh_5")]
    report = cast_report(lines, c)
    assert report.missing == {"Fremder": 1}
    assert report.usage == {"lena": 2, "leon": 1}
```

`generator/tests/test_pipeline_cast.py`:
```python
from drova_voice.cli import main


def test_cast_check_ok(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check"]) == 0
    out = capsys.readouterr().out
    assert "lena: 2" in out and "leon: 1" in out and "ohne Stimme: keine" in out


def test_cast_check_reports_missing_speaker(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check"]) == 1
    assert "Mira: 2" in capsys.readouterr().out


def test_cast_check_unknown_voice_fails_before_running(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers:\n  mira: {voice: erfunden}\n", encoding="utf-8")
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check"]) == 2
    assert "erfunden" in capsys.readouterr().err
```

- [ ] **Step 2: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_casting.py tests/test_pipeline_cast.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.casting`).

- [ ] **Step 3: `casting.py` schreiben**

`generator/drova_voice/casting.py`:
```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line


@dataclass(frozen=True)
class Casting:
    default_player: str
    speakers: dict[str, str]  # Sprechername (klein) -> Stimmenschlüssel aus fish_voices.yaml

    def voice_for(self, line: Line) -> str | None:
        if line.category == "player":
            return self.default_player
        return self.speakers.get(line.actor.lower())


@dataclass(frozen=True)
class CastReport:
    missing: dict[str, int]  # Sprecher ohne Stimme -> Zeilenzahl
    usage: dict[str, int]  # Stimme -> Zeilenzahl


def load_casting(path: Path, voices: Mapping[str, FishVoice]) -> Casting:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Datei muss aus 'Schlüssel: Wert'-Zeilen bestehen")
    default_player = str(raw.get("default_player") or "").lower()
    if default_player not in voices:
        raise ValueError(f"{path}: default_player '{default_player}' fehlt oder steht nicht in fish_voices.yaml")
    speakers: dict[str, str] = {}
    for name, spec in (raw.get("speakers") or {}).items():
        key = str(name).lower()
        voice = str((spec or {}).get("voice", "")).lower()
        if key in speakers:
            raise ValueError(f"{path}: Sprecher '{name}' ist doppelt (Groß-/Kleinschreibung zählt nicht)")
        if voice not in voices:
            raise ValueError(f"{path}: Unbekannte Stimme '{voice}' für Sprecher '{name}' (Schlüssel aus casting/fish_voices.yaml)")
        speakers[key] = voice
    return Casting(default_player, speakers)


def cast_report(lines: Sequence[Line], casting: Casting) -> CastReport:
    missing: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    for line in lines:
        if line.skip:
            continue
        voice = casting.voice_for(line)
        if voice is None:
            missing[line.actor or "(ohne Sprecher)"] += 1
        else:
            usage[voice] += 1
    return CastReport(dict(missing), dict(usage))
```

`casting/casting.yaml` (vorläufig; der Nutzer prüft im Hörtest, Task 9):
```yaml
# Sprecher -> Stimme (Schlüssel aus casting/fish_voices.yaml). Sprechernamen ohne Beachtung der Schreibung.
# VORLÄUFIG: Zuordnung für den Durchstich; der Nutzer entscheidet nach dem Hörtest (Plan 3, Task 9).
default_player: leon      # alle Spielerzeilen (Auswahloptionen); Stimmsets folgen in M5
speakers:
  adela: {voice: melanie}
```

- [ ] **Step 4: `cast` in `pipeline.py` verdrahten**

In `pipeline.py` die Importe ergänzen:
```python
from drova_voice.casting import cast_report, load_casting
from drova_voice.fish_voices import load_fish_voices
```
Neue Funktion vor `HANDLERS`:
```python
def _load_casting(cfg: Config):
    voices = load_fish_voices(cfg.casting_dir / "fish_voices.yaml")
    return voices, load_casting(cfg.casting_dir / "casting.yaml", voices)


def _cast(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        _, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    report = cast_report(lines, casting)
    print("Stimmen (Zeilen): " + (", ".join(f"{v}: {n}" for v, n in sorted(report.usage.items())) or "keine"))
    print("Sprecher ohne Stimme: " + (", ".join(f"{a}: {n}" for a, n in sorted(report.missing.items())) or "keine"))
    return 1 if report.missing else 0
```
In `HANDLERS` den Eintrag `"cast": _cast,` ergänzen; in `add_parsers`:
```python
    cast = sub.add_parser("cast", help="Prüft, ob jeder Sprecher eine Stimme hat (casting/casting.yaml)")
    cast.add_argument("--check", action="store_true", help="nur prüfen (Standard und einzige Betriebsart in Plan 3)")
    cast.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
```
Außerdem im `extract`-Parser nichts ändern.

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add generator casting/casting.yaml
git commit -m "Add the casting step: speaker to voice mapping and cast --check"
```

---

### Task 3: Emotionen (`emote`)

**Files:**
- Create: `generator/drova_voice/emote.py`, `casting/emotions.jsonl` (leere Datei)
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_emote.py`, `generator/tests/test_pipeline_emote.py`

**Interfaces:**
- Consumes: `emotions.EmotionTag/Event/from_stage_directions`, `speech_text.StageDirection`, `lines.Line`, `jsonl.write_jsonl/read_jsonl_lenient`.
- Produces: `emote.merge_emotions(existing: dict[str, EmotionTag], lines: Sequence[Line]) -> dict[str, EmotionTag]`, `emote.read_emotions(path: Path) -> dict[str, EmotionTag]` (fehlende Datei → `{}`; ungültige Zeile → `ValueError` mit Zeilennummer), `emote.write_emotions(path: Path, emotions: Mapping[str, EmotionTag]) -> None` (nach ID sortiert, Zeile = `{"id": ..., **tag.to_dict()}`), `pipeline._emote`. Regel: Zeilen mit `source` `llm` oder `manual` bleiben unverändert; `stage`-Zeilen der gewählten Zeilen werden neu berechnet; Zeilen außerhalb der Auswahl bleiben unberührt.

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_emote.py`:
```python
import pytest

from drova_voice.emote import merge_emotions, read_emotions, write_emotions
from drova_voice.emotions import EmotionTag, Event
from drova_voice.lines import Line


def line(key, stage=(), skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor="Mira", category="dialog", generic=False, raw="x", speech="x" if not skip else "", stage=tuple(stage), skip=skip)


def test_stage_directions_become_tags():
    result = merge_emotions({}, [line("Plh_1", [{"text": "seufzt", "pos": 0}]), line("Plh_2")])
    assert list(result) == ["T|P|Plh_1"]
    tag = result["T|P|Plh_1"]
    assert tag.source == "stage" and [(e.tag, e.pos) for e in tag.events] == [("sigh", 0)]


def test_llm_and_manual_rows_are_kept_over_stage_rows():
    llm = EmotionTag("stern", 0.6, source="llm")
    result = merge_emotions({"T|P|Plh_1": llm}, [line("Plh_1", [{"text": "seufzt", "pos": 0}])])
    assert result["T|P|Plh_1"] is llm


def test_stale_stage_rows_are_dropped_and_other_rows_untouched():
    old_stage = EmotionTag("joyful", 0.3, source="stage")
    outside = EmotionTag("sad", 0.5, source="stage")
    existing = {"T|P|Plh_1": old_stage, "X|Q|Plh_9": outside}
    result = merge_emotions(existing, [line("Plh_1")])  # Regieanweisung ist weggefallen
    assert "T|P|Plh_1" not in result and result["X|Q|Plh_9"] is outside


def test_skipped_lines_get_no_tag():
    assert merge_emotions({}, [line("Plh_1", [{"text": "seufzt", "pos": 0}], skip="gvar")]) == {}


def test_roundtrip_sorted_and_validated(tmp_path):
    path = tmp_path / "emotions.jsonl"
    write_emotions(path, {"B|P|Plh_2": EmotionTag("sad", 0.5, source="llm"),
                          "A|P|Plh_1": EmotionTag("stern", 0.4, [Event("sigh", 3)], ["nie"], source="manual")})
    ids = [l.split('"')[3] for l in path.read_text(encoding="utf-8").splitlines()]
    assert ids == ["A|P|Plh_1", "B|P|Plh_2"]
    back = read_emotions(path)
    assert back["A|P|Plh_1"].events == [Event("sigh", 3)] and back["A|P|Plh_1"].emphasis == ["nie"]


def test_read_rejects_unknown_emotion_with_line_number(tmp_path):
    path = tmp_path / "emotions.jsonl"
    path.write_text('{"id": "a", "emotion": "neutral"}\n{"id": "b", "emotion": "verwirrt", "intensity": 0.5}\n',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="Zeile 2"):
        read_emotions(path)


def test_read_missing_file_is_empty(tmp_path):
    assert read_emotions(tmp_path / "gibt-es-nicht.jsonl") == {}
```

`generator/tests/test_pipeline_emote.py`:
```python
from drova_voice.cli import main
from drova_voice.emote import read_emotions


def test_emote_writes_stage_rows(pipeline_repo, capsys):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "emote"]) == 0
    emotions = read_emotions(pipeline_repo.casting / "emotions.jsonl")
    assert list(emotions) == ["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1"]
    assert "stage: 1" in capsys.readouterr().out


def test_emote_keeps_llm_rows_on_rerun(pipeline_repo):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    path = pipeline_repo.casting / "emotions.jsonl"
    path.write_text('{"id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2", "emotion": "stern", "intensity": 0.5, "source": "llm"}\n',
                    encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "emote"]) == 0
    emotions = read_emotions(path)
    assert emotions["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2"].source == "llm"
    assert emotions["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1"].source == "stage"
```

- [ ] **Step 2: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_emote.py tests/test_pipeline_emote.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.emote`).

- [ ] **Step 3: `emote.py` schreiben**

`generator/drova_voice/emote.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.emotions import EmotionTag, from_stage_directions
from drova_voice.jsonl import write_jsonl
from drova_voice.lines import Line
from drova_voice.speech_text import StageDirection

KEEP_SOURCES = ("llm", "manual")


def merge_emotions(existing: Mapping[str, EmotionTag], lines: Sequence[Line]) -> dict[str, EmotionTag]:
    """Regieanweisungen -> Tags für die gewählten Zeilen; llm/manual-Zeilen und alles außerhalb der Auswahl bleibt."""
    selected = {l.id for l in lines}
    result = {i: t for i, t in existing.items() if i not in selected or t.source in KEEP_SOURCES}
    for line in lines:
        if line.skip or line.id in result or not line.stage:
            continue
        tag = from_stage_directions([StageDirection(s["text"], int(s["pos"])) for s in line.stage])
        if tag.source == "stage":
            result[line.id] = tag
    return result


def read_emotions(path: Path) -> dict[str, EmotionTag]:
    path = Path(path)
    if not path.exists():
        return {}
    result: dict[str, EmotionTag] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
            result[row["id"]] = EmotionTag.from_dict(row)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{path}: Zeile {number} ungültig ({e})") from e
    return result


def write_emotions(path: Path, emotions: Mapping[str, EmotionTag]) -> None:
    write_jsonl(path, ({"id": i, **emotions[i].to_dict()} for i in sorted(emotions)))
```

`casting/emotions.jsonl`: leere Datei anlegen (`: > casting/emotions.jsonl` in Bash).

- [ ] **Step 4: `emote` in `pipeline.py` verdrahten**

Importe ergänzen: `from collections import Counter` ist schon da; ergänzen:
```python
from drova_voice.emote import merge_emotions, read_emotions, write_emotions
```
Funktion vor `HANDLERS`:
```python
def emotions_path(cfg: Config) -> Path:
    return cfg.casting_dir / "emotions.jsonl"


def _emote(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        merged = merge_emotions(read_emotions(emotions_path(cfg)), lines)
    except ValueError as e:
        return _fail(str(e))
    write_emotions(emotions_path(cfg), merged)
    sources = Counter(t.source for t in merged.values())
    print(f"{len(merged)} Emotionen -> {emotions_path(cfg)}; " + ", ".join(f"{s}: {n}" for s, n in sorted(sources.items())))
    return 0
```
`HANDLERS`: `"emote": _emote,`. `add_parsers`:
```python
    em = sub.add_parser("emote", help="Emotionen aus Regieanweisungen nach casting/emotions.jsonl (llm/manual bleiben)")
    em.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
```

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add generator casting/emotions.jsonl
git commit -m "Add the emote step: stage-direction emotions merged with llm and manual rows"
```

---

### Task 4: `synth` (Aufträge, Cache, Plausibilität, paralleler Lauf)

**Files:**
- Create: `generator/drova_voice/synth.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_synth.py`, `generator/tests/test_pipeline_synth.py`

**Interfaces:**
- Consumes: `render.render_request(engine, text, tag) -> (text, params)`, `engines.client.EngineClient/EngineError/worker_command/cache_env` (Client hat `.synth(req) -> SynthResponse` und `.model`), `engines.protocol.SynthRequest/SynthResponse`, `jsonl.replace_with_retry/append_jsonl`, `casting.Casting`, `fish_voices.FishVoice`, `emote.read_emotions`.
- Produces:
  - `synth.SynthJob(id: str, text: str, speech_len: int, voice: str | None, params: dict)`.
  - `synth.SynthResult(id, key, wav, duration, ok, attempts, flagged, error)` mit `to_dict()`.
  - `synth.SKIP_NO_VOICE = "no_voice"`.
  - `synth.build_jobs(lines, casting, fish_table, emotions, engine) -> (list[SynthJob], dict[str, str])` (zweiter Wert: Zeilen-ID → Grund fürs Überspringen).
  - `synth.make_key(engine, model, voice, text, params) -> str` (32 Hex), `synth.plausible(duration, speech_len) -> bool`, `synth.wav_duration(path) -> float`.
  - `synth.run_synth(jobs, engine, client_factory, cache_dir, workers=8, on_result=None) -> list[SynthResult]` (`client_factory(engine)` liefert einen Kontextmanager mit Client; ein Client je Strang; gleiche Cache-Schlüssel werden nur einmal erzeugt; WAVs landen als `<cache_dir>/<key>.wav`).
  - `pipeline.synth_results_path(cfg) -> Path` (`data/synth/results.jsonl`), `pipeline._synth`.

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_synth.py`:
```python
import contextlib
import threading
import wave

import pytest

from drova_voice.casting import Casting
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineError
from drova_voice.engines.protocol import SynthResponse
from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line
from drova_voice.synth import (SKIP_NO_VOICE, SynthJob, build_jobs, make_key, plausible, run_synth, wav_duration)

FISH = {"lena": FishVoice("lena", "a" * 32, "Lena", "f", "de"), "leon": FishVoice("leon", "b" * 32, "Leon", "m", "de")}
CASTING = Casting("leon", {"mira": "lena"})


def line(key, speech="Der Weg nach Norden ist weit.", actor="Mira", category="dialog", skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw=speech, speech=speech, stage=(), skip=skip)


class StubClient:
    """Schreibt eine WAV-Datei mit fester Dauer; zählt Aufrufe."""
    model = "stub-1"

    def __init__(self, calls, seconds=2.0, fail_on=None, die_on=None):
        self.calls, self.seconds, self.fail_on, self.die_on = calls, seconds, fail_on, die_on
        self.lock = threading.Lock()

    def synth(self, req):
        with self.lock:
            self.calls.append(req.id)
        if self.die_on and self.die_on in req.text:
            raise EngineError("Worker beendet")
        if self.fail_on and self.fail_on in req.text:
            return SynthResponse(req.id, False, error="HTTP 500")
        rate = 8000
        with wave.open(req.out_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"\x00\x00" * int(rate * self.seconds))
        return SynthResponse(req.id, True, req.out_path, rate, self.seconds)


def factory(calls, **kw):
    return lambda engine: contextlib.nullcontext(StubClient(calls, **kw))


def job(id_, text="Der Weg nach Norden ist weit.", voice=None):
    return SynthJob(id_, text, len(text), voice, {})


def test_build_jobs_skips_and_maps_voices():
    lines = [line("Plh_1"), line("Plh_2", skip="gvar", speech=""), line("Plh_3", actor="Fremder"),
             line("Plh_4", actor="Player", category="player"), line("Plh_5", speech="…")]
    jobs, skipped = build_jobs(lines, CASTING, FISH, {}, "fish")
    assert [(j.id, j.voice) for j in jobs] == [("T|P|Plh_1", "a" * 32), ("T|P|Plh_4", "b" * 32)]
    assert skipped == {"T|P|Plh_2": "gvar", "T|P|Plh_3": SKIP_NO_VOICE, "T|P|Plh_5": "unspeakable"}


def test_build_jobs_renders_emotion_for_fish_and_ignores_voice_for_fake():
    emotions = {"T|P|Plh_1": EmotionTag("sad", 0.5, source="llm")}
    (j,), _ = build_jobs([line("Plh_1")], CASTING, FISH, emotions, "fish")
    assert j.text.startswith("[sad] ")
    (j2,), _ = build_jobs([line("Plh_1")], CASTING, FISH, emotions, "fake")
    assert j2.voice is None and j2.text == "Der Weg nach Norden ist weit."


def test_make_key_depends_on_every_input():
    base = make_key("fish", "m1", "v1", "Text", {})
    assert base == make_key("fish", "m1", "v1", "Text", {})
    assert len({base, make_key("fake", "m1", "v1", "Text", {}), make_key("fish", "m2", "v1", "Text", {}),
                make_key("fish", "m1", "v2", "Text", {}), make_key("fish", "m1", "v1", "Anderer", {}),
                make_key("fish", "m1", "v1", "Text", {"x": 1})}) == 6


def test_plausible_bounds():
    assert plausible(2.0, 34)  # 34 Zeichen ~ 2 s
    assert not plausible(0.1, 34) and not plausible(None, 34)
    assert not plausible(30.0, 34)  # viel zu lang (Halluzination)
    assert plausible(0.6, 5) and not plausible(9.0, 5)  # sehr kurze Zeilen: nur Obergrenze


def test_run_synth_writes_cache_and_second_run_makes_no_calls(tmp_path):
    calls = []
    results = run_synth([job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory(calls), tmp_path, workers=2)
    assert sorted(r.id for r in results) == ["a", "b"] and all(r.ok and not r.flagged for r in results)
    assert all(wav_duration(r.wav) == pytest.approx(2.0, abs=0.01) for r in results)
    assert len(calls) == 2
    again = run_synth([job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory(calls), tmp_path, workers=2)
    assert len(calls) == 2 and all(r.ok and r.attempts == 0 for r in again)


def test_identical_text_is_synthesized_once(tmp_path):
    calls = []
    results = run_synth([job("a"), job("b")], "fake", factory(calls), tmp_path, workers=2)
    assert len(calls) == 1 and {r.id for r in results} == {"a", "b"} and all(r.ok for r in results)


def test_stale_part_file_is_ignored_and_no_part_files_remain(tmp_path):
    key = make_key("fake", "stub-1", None, "Der Weg nach Norden ist weit.", {})
    (tmp_path / f"{key}.part.wav").write_bytes(b"halbe Datei")  # Rest eines abgebrochenen Laufs
    (r,) = run_synth([job("a")], "fake", factory([]), tmp_path)
    assert r.ok and wav_duration(r.wav) == pytest.approx(2.0, abs=0.01)
    assert list(tmp_path.glob("*.part.wav")) == []


def test_implausible_duration_is_retried_then_flagged(tmp_path):
    calls = []
    (r,) = run_synth([job("a")], "fake", factory(calls, seconds=40.0), tmp_path)
    assert r.ok and r.flagged and r.attempts == 3 and len(calls) == 3


def test_api_error_is_reported_without_wav(tmp_path):
    (r,) = run_synth([job("a", "Das schlägt FEHL.")], "fake", factory([], fail_on="FEHL"), tmp_path)
    assert not r.ok and "HTTP 500" in r.error and r.wav is None
    assert list(tmp_path.glob("*.wav")) == []


def test_dead_worker_fails_remaining_jobs_instead_of_hanging(tmp_path):
    jobs = [job("a", "Das ist STOPP hier."), job("b", "Danach kommt noch etwas."), job("c", "Und noch etwas anderes.")]
    results = run_synth(jobs, "fake", factory([], die_on="STOPP"), tmp_path, workers=1)
    by_id = {r.id: r for r in results}
    assert not by_id["a"].ok and "Worker beendet" in by_id["a"].error
    assert not by_id["b"].ok and not by_id["c"].ok


def test_on_result_is_called_for_each_job(tmp_path):
    seen = []
    run_synth([job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory([]), tmp_path, workers=2, on_result=seen.append)
    assert sorted(r.id for r in seen) == ["a", "b"]
```

`generator/tests/test_pipeline_synth.py`:
```python
from drova_voice.cli import main
from drova_voice.jsonl import latest_by_id, read_jsonl_lenient

NPC_TREE = "DT_Test_NPC_Mira|Dialog/NPC_Mira|"


def run(pipeline_repo, *args):
    return main(["--config", str(pipeline_repo.cfg), *args])


def test_synth_fake_engine_writes_results_and_cache(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--workers", "2")) == 0
    rows = latest_by_id(read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl"))
    assert sorted(rows) == [NPC_TREE + "Plh_1", NPC_TREE + "Plh_2", NPC_TREE + "Plh_3|c0"]
    assert all(r["ok"] for r in rows.values())
    assert len(list((pipeline_repo.repo / "cache" / "synth").glob("*.wav"))) == 3
    out = capsys.readouterr().out
    assert "3 erzeugt" in out and "übersprungen: gvar: 1, unspeakable: 1" in out


def test_synth_second_run_uses_the_cache(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    capsys.readouterr()
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    assert "0 neu erzeugt" in capsys.readouterr().out


def test_synth_reports_speaker_without_voice(pipeline_repo, guarded, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    assert "no_voice: 2" in capsys.readouterr().out


def test_synth_limit(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--limit", "1")) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl")
    assert len(rows) == 1
```
(`stimmen ohne Stimme` erzeugt keinen Fehlercode: sie zählen als übersprungen; `cast --check` ist die Prüfung, die scheitert.)

- [ ] **Step 2: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_synth.py tests/test_pipeline_synth.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.synth`).

- [ ] **Step 3: `synth.py` schreiben**

`generator/drova_voice/synth.py`:
```python
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
from drova_voice.lines import SKIP_UNSPEAKABLE, Line
from drova_voice.render import render_request

SKIP_NO_VOICE = "no_voice"

# Fish, Deutsch, gemessen 2026-10-12 (docs/decisions/2026-10-fish-throughput.md): 37.068 Zeichen -> 2.169 s Audio.
CHARS_PER_SECOND = 17.0
MIN_RATIO, MAX_RATIO = 0.4, 2.5  # Dauer / erwartete Dauer
MIN_SECONDS = 0.25
SHORT_EXPECTED_SECONDS = 1.0  # darunter gilt nur die Obergrenze
SHORT_MAX_SECONDS = 5.0
MAX_ATTEMPTS = 3


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
            text, params = render_request(engine, line.speech, emotions.get(line.id, EmotionTag()))
        except ValueError:
            skipped[line.id] = SKIP_UNSPEAKABLE
            continue
        jobs.append(SynthJob(line.id, text, len(line.speech), voice, params))
    return jobs, skipped


def synth_one(client, job: SynthJob, key: str, cache_dir: Path, max_attempts: int = MAX_ATTEMPTS) -> SynthResult:
    wav = Path(cache_dir) / f"{key}.wav"
    if wav.exists():  # Cache-Treffer: nur fertige Dateien liegen unter dem endgültigen Namen
        duration = wav_duration(wav)
        return SynthResult(job.id, key, str(wav), duration, True, 0, not plausible(duration, job.speech_len), None)
    wav.parent.mkdir(parents=True, exist_ok=True)
    part = wav.with_name(f"{key}.part.wav")
    duration: float | None = None
    error: str | None = None
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        resp = client.synth(SynthRequest(id=job.id, text=job.text, out_path=str(part), voice=job.voice, params=job.params))
        if not resp.ok:
            error, duration = resp.error or "unbekannter Fehler", None
            part.unlink(missing_ok=True)
            continue
        error, duration = None, resp.duration
        if plausible(duration, job.speech_len):
            break
    if duration is None:
        return SynthResult(job.id, key, None, None, False, attempt, False, error)
    replace_with_retry(part, wav)
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
              on_result: Callable[[SynthResult], None] | None = None) -> list[SynthResult]:
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

        def emit(r: SynthResult) -> None:
            with lock:
                results.append(r)
                if on_result is not None:
                    on_result(r)

        def work(job: SynthJob) -> None:
            key = keys[job.id]
            client = _acquire(idle, alive, lock)
            if client is None:
                r = SynthResult(job.id, key, None, None, False, 0, False, "kein Worker mehr verfügbar")
            else:
                try:
                    r = synth_one(client, job, key, cache_dir)
                except EngineError as e:  # Worker tot: nicht zurücklegen, Rest dieses Laufs scheitert sauber
                    with lock:
                        alive[0] -= 1
                    r = SynthResult(job.id, key, None, None, False, 0, False, str(e))
                else:
                    idle.put(client)
            emit(r)
            for other in followers.get(key, []):
                emit(SynthResult(other.id, key, r.wav, r.duration, r.ok, 0, r.flagged, r.error))

        with ThreadPoolExecutor(max_workers=len(clients)) as pool:
            list(pool.map(work, first_by_key.values()))
    return results
```

- [ ] **Step 4: `synth` in `pipeline.py` verdrahten**

Importe ergänzen:
```python
from drova_voice.engines.client import EngineClient, EngineError, cache_env, worker_command
from drova_voice.jsonl import append_jsonl, latest_by_id, read_jsonl_lenient
from drova_voice.synth import build_jobs, run_synth
```
Funktionen vor `HANDLERS`:
```python
def synth_results_path(cfg: Config) -> Path:
    return cfg.data_dir / "synth" / "results.jsonl"


def _client_factory(cfg: Config):
    def make(engine: str) -> EngineClient:
        return EngineClient(worker_command(WORKERS_DIR, engine), env=cache_env(cfg.cache_dir))
    return make


def _synth(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        voices, casting = _load_casting(cfg)
        emotions = read_emotions(emotions_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    jobs, skipped = build_jobs(lines, casting, voices, emotions, args.engine)
    if args.limit:
        jobs = jobs[: args.limit]
    cache_dir = cfg.cache_dir / "synth"
    path = synth_results_path(cfg)
    results = run_synth(jobs, args.engine, _client_factory(cfg), cache_dir, args.workers,
                        on_result=lambda r: append_jsonl(path, r.to_dict()))
    done = [r for r in results if r.ok]
    new = [r for r in done if r.attempts > 0]
    failed = [r for r in results if not r.ok]
    flagged = [r for r in done if r.flagged]
    reasons = Counter(skipped.values())
    detail = ", ".join(f"{k}: {n}" for k, n in sorted(reasons.items())) or "keine"
    print(f"{len(done)} erzeugt ({len(done) - len(new)} aus dem Cache, {len(new)} neu erzeugt), {len(failed)} Fehler, "
          f"{len(flagged)} auffällige Dauer; übersprungen: {detail}")
    for r in failed[:10]:
        print(f"FEHLER {r.id}: {r.error}", file=sys.stderr)
    for r in flagged[:10]:
        print(f"AUFFÄLLIG {r.id}: Dauer {r.duration:.1f} s", file=sys.stderr)
    return 1 if failed else 0
```
Die Zeile `"{len(done)} erzeugt (...)"` enthält „neu erzeugt“; die Tests prüfen `3 erzeugt` und `0 neu erzeugt`.
`HANDLERS`: `"synth": _synth,`. `add_parsers`:
```python
    sy = sub.add_parser("synth", help="Sprache erzeugen (Cache unter cache/synth, wiederaufnehmbar)")
    sy.add_argument("--engine", default="fish")
    sy.add_argument("--workers", type=int, default=8, help="parallele Anfragen (Standard 8, gemessen ohne 429 bis 16)")
    sy.add_argument("--limit", type=int, help="nur die ersten N Aufträge (zum Ausprobieren)")
    sy.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
```
(`EngineError` aus dem Import wird in `cli.main` bereits abgefangen; in `pipeline.py` wird er nicht gebraucht – den Import weglassen, falls ein Linter meckert.)

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add generator
git commit -m "Add the synth step: parallel resumable synthesis with a content-addressed cache"
```

---

### Task 5: `encode` (ffmpeg: trimmen, Lautheit, OGG)

**Files:**
- Create: `generator/drova_voice/encode.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_encode.py`, `generator/tests/test_pipeline_encode.py`

**Interfaces:**
- Consumes: `ids.audio_filename`, `lines.Line`, `emotions.EmotionTag` (`notes` enthält z. B. `"whisper"`), `jsonl.replace_with_retry/write_jsonl`, `synth_results_path`.
- Produces:
  - `encode.rel_audio_path(line: Line) -> str` (`"<kategorie>/<sha1[:16]>.ogg"`, Spielerzeilen: `"player/default/<…>.ogg"`).
  - `encode.build_filter(notes: Sequence[str]) -> str`, `encode.ffmpeg_command(ffmpeg: str, src: Path, dst: Path, notes) -> list[str]`.
  - `encode.find_tools() -> tuple[str, str]` (ffmpeg, ffprobe; `ValueError` auf Deutsch, wenn eines fehlt oder ffmpeg kein `libvorbis` hat).
  - `encode.encode_one(ffmpeg, ffprobe, wav: Path, dst: Path, notes, key: str) -> float` (Dauer der OGG-Datei; überspringt, wenn `dst` mit gleichem Stempel existiert).
  - `encode.run_encode(lines, synth_rows: Mapping[str, dict], emotions, audio_dir: Path, workers: int) -> tuple[list[dict], list[str]]` (Zeilen `{"id", "rel", "duration", "key"}` und Fehlertexte).
  - `pipeline.encoded_path(cfg) -> Path` (`data/encoded.jsonl`), `pipeline._encode`.

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_encode.py`:
```python
import shutil
import wave
import math
import struct

import pytest

from drova_voice.emotions import EmotionTag
from drova_voice.encode import (build_filter, encode_one, ffmpeg_command, find_tools, probe_duration, rel_audio_path,
                                run_encode)
from drova_voice.ids import audio_filename
from drova_voice.lines import Line

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


def line(key="Plh_1", category="dialog"):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor="Mira", category=category, generic=False, raw="x", speech="x", stage=(), skip=None)


def sine_wav(path, seconds=1.0, lead_silence=0.3, rate=22050):
    frames = []
    for i in range(int(rate * (lead_silence + seconds))):
        v = 0 if i < rate * lead_silence else int(8000 * math.sin(2 * math.pi * 220 * i / rate))
        frames.append(struct.pack("<h", v))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(frames))


def test_rel_audio_path_by_category():
    l = line("Plh_1")
    assert rel_audio_path(l) == f"dialog/{audio_filename(l.id)}"
    p = line("Plh_2", "player")
    assert rel_audio_path(p) == f"player/default/{audio_filename(p.id)}"
    assert rel_audio_path(line("Plh_3", "bark")).startswith("bark/")


def test_filter_chain_and_whisper():
    base = build_filter([])
    assert "silenceremove" in base and "loudnorm=I=-16" in base and "volume=" not in base
    assert build_filter(["whisper"]).endswith("volume=-6dB")
    assert build_filter(["drunk"]) == base  # unbekannte Hinweise ändern nichts


def test_ffmpeg_command_shape(tmp_path):
    cmd = ffmpeg_command("ffmpeg", tmp_path / "a.wav", tmp_path / "a.ogg", [])
    assert cmd[0] == "ffmpeg" and "libvorbis" in cmd and cmd[cmd.index("-ac") + 1] == "1" and cmd[-1].endswith("a.ogg")


def test_find_tools_reports_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr("drova_voice.encode.shutil.which", lambda name: None)
    with pytest.raises(ValueError, match="ffmpeg"):
        find_tools()


@needs_ffmpeg
def test_encode_one_trims_silence_and_is_resumable(tmp_path):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, seconds=1.0, lead_silence=0.5)
    dst = tmp_path / "out" / "dialog" / "x.ogg"
    duration = encode_one(ffmpeg, ffprobe, wav, dst, [], "key1")
    assert dst.is_file() and 0.8 < duration < 1.3  # Stille vorn ist weg (vorher 1,5 s)
    stamp_before = dst.stat().st_mtime_ns
    assert encode_one(ffmpeg, ffprobe, wav, dst, [], "key1") == pytest.approx(duration, abs=0.01)
    assert dst.stat().st_mtime_ns == stamp_before  # nichts neu kodiert
    encode_one(ffmpeg, ffprobe, wav, dst, ["whisper"], "key1")  # anderer Hinweis -> neu kodiert
    assert dst.stat().st_mtime_ns != stamp_before
    assert list((tmp_path / "out" / "dialog").glob("*.part.ogg")) == []
    assert probe_duration(ffprobe, dst) > 0


@needs_ffmpeg
def test_run_encode_collects_rows_and_errors(tmp_path):
    wav = tmp_path / "a.wav"
    sine_wav(wav)
    lines = [line("Plh_1"), line("Plh_2"), line("Plh_3")]
    synth_rows = {"T|P|Plh_1": {"id": "T|P|Plh_1", "ok": True, "wav": str(wav), "key": "k1"},
                  "T|P|Plh_2": {"id": "T|P|Plh_2", "ok": True, "wav": str(tmp_path / "weg.wav"), "key": "k2"}}
    rows, errors = run_encode(lines, synth_rows, {"T|P|Plh_1": EmotionTag("neutral", 0.0, source="llm")},
                              tmp_path / "audio", workers=2)
    assert [r["id"] for r in rows] == ["T|P|Plh_1"] and rows[0]["rel"] == rel_audio_path(lines[0])
    assert (tmp_path / "audio" / rows[0]["rel"]).is_file()
    assert len(errors) == 1 and "Plh_2" in errors[0]  # WAV fehlt; Plh_3 hat gar keine Synth-Zeile und zählt nicht als Fehler
```

`generator/tests/test_pipeline_encode.py`:
```python
import shutil

import pytest

from drova_voice.cli import main
from drova_voice.jsonl import read_jsonl_lenient

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


@needs_ffmpeg
def test_encode_after_synth(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    assert guarded(lambda: main(base + ["synth", "--engine", "fake"])) == 0
    capsys.readouterr()
    assert guarded(lambda: main(base + ["encode", "--workers", "2"])) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "encoded.jsonl")
    assert len(rows) == 3 and all(r["duration"] > 0.2 for r in rows)
    ogg = sorted((pipeline_repo.repo / "out" / "audio" / "de").rglob("*.ogg"))
    assert len(ogg) == 3 and {p.parent.name for p in ogg} == {"dialog", "default"}
    assert "3 kodiert" in capsys.readouterr().out


def test_encode_without_synth_results_fails_clearly(pipeline_repo, capsys):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "encode"]) == 2
    assert "synth" in capsys.readouterr().err
```

- [ ] **Step 2: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_encode.py tests/test_pipeline_encode.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.encode`).

- [ ] **Step 3: `encode.py` schreiben**

`generator/drova_voice/encode.py`:
```python
from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.emotions import EmotionTag
from drova_voice.ids import audio_filename
from drova_voice.jsonl import replace_with_retry
from drova_voice.lines import Line

_TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
WHISPER_GAIN_DB = -6


def rel_audio_path(line: Line) -> str:
    folder = "player/default" if line.category == "player" else line.category
    return f"{folder}/{audio_filename(line.id)}"


def build_filter(notes: Sequence[str]) -> str:
    # Stille vorn und hinten entfernen (hinten: Umkehren, vorn trimmen, zurückdrehen), dann auf -16 LUFS.
    parts = [_TRIM, "areverse", _TRIM, "areverse", LOUDNORM]
    if "whisper" in notes:  # *flüstert*: leiser (das "gehauchte" kommt später, falls der Hörtest es verlangt)
        parts.append(f"volume={WHISPER_GAIN_DB}dB")
    return ",".join(parts)


def ffmpeg_command(ffmpeg: str, src: Path, dst: Path, notes: Sequence[str]) -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", build_filter(notes),
            "-ac", "1", "-c:a", "libvorbis", "-q:a", "4", str(dst)]


def find_tools() -> tuple[str, str]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("ffmpeg/ffprobe nicht gefunden (müssen im PATH liegen)")
    encoders = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, errors="replace")
    if "libvorbis" not in encoders.stdout:
        raise ValueError("Dieses ffmpeg kann kein OGG Vorbis (Encoder libvorbis fehlt)")
    return ffmpeg, ffprobe


def probe_duration(ffprobe: str, path: Path) -> float:
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _stamp(key: str, notes: Sequence[str]) -> str:
    return f"{key}|{build_filter(notes)}"


def encode_one(ffmpeg: str, ffprobe: str, wav: Path, dst: Path, notes: Sequence[str], key: str) -> float:
    dst = Path(dst)
    stamp_file = dst.with_suffix(".stamp")
    stamp = _stamp(key, notes)
    if dst.is_file() and stamp_file.is_file() and stamp_file.read_text(encoding="utf-8") == stamp:
        return probe_duration(ffprobe, dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(f"{dst.stem}.part.ogg")
    proc = subprocess.run(ffmpeg_command(ffmpeg, Path(wav), part, notes), capture_output=True, text=True, errors="replace")
    if proc.returncode != 0 or not part.is_file():
        part.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg Exit-Code {proc.returncode}: {proc.stderr.strip()[:200]}")
    replace_with_retry(part, dst)
    stamp_file.write_text(stamp, encoding="utf-8")
    return probe_duration(ffprobe, dst)


def run_encode(lines: Sequence[Line], synth_rows: Mapping[str, dict], emotions: Mapping[str, EmotionTag],
               audio_dir: Path, workers: int = 4) -> tuple[list[dict], list[str]]:
    ffmpeg, ffprobe = find_tools()
    todo = [(l, synth_rows[l.id]) for l in lines if l.id in synth_rows and synth_rows[l.id].get("ok")]

    def work(item):
        line, row = item
        wav = Path(row["wav"] or "")
        if not wav.is_file():
            return None, f"{line.id}: WAV fehlt ({wav})"
        notes = emotions[line.id].notes if line.id in emotions else []
        rel = rel_audio_path(line)
        try:
            duration = encode_one(ffmpeg, ffprobe, wav, Path(audio_dir) / rel, notes, row["key"])
        except (RuntimeError, OSError, ValueError) as e:
            return None, f"{line.id}: {e}"
        return {"id": line.id, "rel": rel, "duration": round(duration, 3), "key": row["key"]}, None

    rows: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for row, error in pool.map(work, todo):
            if row:
                rows.append(row)
            if error:
                errors.append(error)
    return rows, errors
```

- [ ] **Step 4: `encode` in `pipeline.py` verdrahten**

Importe ergänzen:
```python
from drova_voice.encode import find_tools, run_encode
from drova_voice.jsonl import write_jsonl
```
(`write_jsonl` zum bestehenden `jsonl`-Import hinzufügen, falls schon vorhanden zusammenführen.) Funktionen vor `HANDLERS`:
```python
def encoded_path(cfg: Config) -> Path:
    return cfg.data_dir / "encoded.jsonl"


def audio_dir(cfg: Config) -> Path:
    return cfg.out_dir / "audio" / cfg.language


def _encode(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    synth_rows = latest_by_id(read_jsonl_lenient(synth_results_path(cfg)))
    if not synth_rows:
        return _fail(f"{synth_results_path(cfg)} fehlt oder ist leer (zuerst `drova-voice synth` ausführen)")
    try:
        emotions = read_emotions(emotions_path(cfg))
        rows, errors = run_encode(lines, synth_rows, emotions, audio_dir(cfg), args.workers)
    except ValueError as e:
        return _fail(str(e))
    merged = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    merged.update({r["id"]: r for r in rows})
    write_jsonl(encoded_path(cfg), merged.values())
    print(f"{len(rows)} kodiert -> {audio_dir(cfg)}; {len(errors)} Fehler")
    for e in errors[:10]:
        print(f"FEHLER {e}", file=sys.stderr)
    return 1 if errors else 0
```
`HANDLERS`: `"encode": _encode,`. `add_parsers`:
```python
    en = sub.add_parser("encode", help="WAV -> OGG (Stille trimmen, -16 LUFS, mono) nach out/audio/<Sprache>")
    en.add_argument("--workers", type=int, default=4)
    en.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
```

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün (ffmpeg ist installiert, die `needs_ffmpeg`-Tests laufen).

- [ ] **Step 6: Commit**

```bash
git add generator
git commit -m "Add the encode step: trimmed, loudness-normalized OGG per line"
```

---

### Task 6: `install` und `index.json` (plus Dateiformat-Vertrag)

**Files:**
- Create: `generator/drova_voice/install.py`, `docs/audio-format.md`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_install.py`, `generator/tests/test_pipeline_install.py`

**Interfaces:**
- Consumes: encoded rows `{"id","rel","duration","key"}`, `jsonl.replace_with_retry`, `ids.VARIANT_SEP`, `pipeline.encoded_path/audio_dir`.
- Produces:
  - `install.split_variant(full_id: str) -> tuple[str, str | None]`.
  - `install.install_audio(rows: Sequence[dict], audio_dir: Path, install_dir: Path, language: str) -> InstallResult` (`copied: int`, `entries: int`, `errors: list[str]`).
  - Format `index.json` (siehe `docs/audio-format.md`): `{"version": 1, "language": "de", "entries": {fullId: {"file": rel, "duration": s}}, "variants": {baseId: [variant, ...]}}`, Schlüssel sortiert, UTF-8 ohne `\u`-Escapes.
  - `pipeline._install`.

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_install.py`:
```python
import json

from drova_voice.install import install_audio, split_variant


def make_audio(audio_dir, rel, content=b"OggS-Test"):
    path = audio_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def row(id_, rel, duration=1.5):
    return {"id": id_, "rel": rel, "duration": duration, "key": "k"}


def read_index(install_dir):
    return json.loads((install_dir / "index.json").read_text(encoding="utf-8"))


def test_split_variant():
    assert split_variant("T|P|Plh_1") == ("T|P|Plh_1", None)
    assert split_variant("T|P|Plh_1#arden") == ("T|P|Plh_1", "arden")
    assert split_variant("T|P|Plh_1|c2#m1") == ("T|P|Plh_1|c2", "m1")


def test_install_copies_files_and_writes_index(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "game" / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "player/default/bbbb.ogg")
    result = install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg", 1.23456), row("T|P|Plh_2|c0", "player/default/bbbb.ogg")],
                           audio, target, "de")
    assert (result.copied, result.entries, result.errors) == (2, 2, [])
    assert (target / "dialog" / "aaaa.ogg").read_bytes() == b"OggS-Test"
    index = read_index(target)
    assert index["version"] == 1 and index["language"] == "de"
    assert index["entries"]["T|P|Plh_1"] == {"file": "dialog/aaaa.ogg", "duration": 1.235}
    assert index["entries"]["T|P|Plh_2|c0"]["file"] == "player/default/bbbb.ogg" and index["variants"] == {}


def test_second_install_keeps_earlier_entries(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/cccc.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    install_audio([row("U|Q|Plh_1", "dialog/cccc.ogg")], audio, target, "de")
    assert sorted(read_index(target)["entries"]) == ["T|P|Plh_1", "U|Q|Plh_1"]


def test_missing_source_is_an_error_and_not_indexed(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    result = install_audio([row("T|P|Plh_1", "dialog/weg.ogg")], audio, target, "de")
    assert result.entries == 0 and len(result.errors) == 1 and "Plh_1" in result.errors[0]
    assert read_index(target)["entries"] == {}


def test_entries_whose_file_vanished_are_dropped(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    (target / "dialog" / "aaaa.ogg").unlink()
    install_audio([], audio, target, "de")
    assert read_index(target)["entries"] == {}


def test_variants_and_umlauts(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/bbbb.ogg")
    install_audio([row("DT_Bär|P|Plh_1#neutral", "dialog/aaaa.ogg"), row("DT_Bär|P|Plh_1#arden", "dialog/bbbb.ogg")],
                  audio, target, "de")
    text = (target / "index.json").read_text(encoding="utf-8")
    assert "DT_Bär" in text and "\\u" not in text
    assert read_index(target)["variants"] == {"DT_Bär|P|Plh_1": ["arden", "neutral"]}


def test_unchanged_files_are_not_copied_again(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    assert install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de").copied == 0
```

`generator/tests/test_pipeline_install.py`:
```python
import json
import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


@needs_ffmpeg
def test_install_after_encode(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    guarded(lambda: main(base + ["synth", "--engine", "fake"]))
    guarded(lambda: main(base + ["encode"]))
    capsys.readouterr()
    assert main(base + ["install", "--npc", "Mira"]) == 0
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert sorted(index["entries"]) == ["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1", "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2",
                                        "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_3|c0"]
    assert len(list(pipeline_repo.install_dir.rglob("*.ogg"))) == 3
    assert "3 Einträge" in capsys.readouterr().out


def test_install_without_encoded_fails_clearly(pipeline_repo, capsys):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "install"]) == 2
    assert "encode" in capsys.readouterr().err
```

- [ ] **Step 2: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_install.py tests/test_pipeline_install.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.install`).

- [ ] **Step 3: `install.py` schreiben**

`generator/drova_voice/install.py`:
```python
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from drova_voice.ids import VARIANT_SEP
from drova_voice.jsonl import replace_with_retry

INDEX_VERSION = 1


@dataclass
class InstallResult:
    copied: int = 0
    entries: int = 0
    errors: list[str] = field(default_factory=list)


def split_variant(full_id: str) -> tuple[str, str | None]:
    base, sep, variant = full_id.partition(VARIANT_SEP)
    return (base, variant) if sep else (full_id, None)


def _load_index(path: Path, language: str) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        index = json.loads(path.read_text(encoding="utf-8-sig"))
        if index.get("version") != INDEX_VERSION or index.get("language") != language:
            return {}
        return dict(index.get("entries", {}))
    except (json.JSONDecodeError, AttributeError, OSError):
        return {}  # kaputter Index: neu aufbauen, die Dateien bleiben liegen


def _same_file(src: Path, dst: Path) -> bool:
    if not dst.is_file():
        return False
    a, b = src.stat(), dst.stat()
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def install_audio(rows: Sequence[dict], audio_dir: Path, install_dir: Path, language: str) -> InstallResult:
    audio_dir, install_dir = Path(audio_dir), Path(install_dir)
    index_path = install_dir / "index.json"
    # frühere Einträge behalten, aber nur solche, deren Datei noch da ist
    entries = {i: e for i, e in _load_index(index_path, language).items() if (install_dir / e.get("file", "")).is_file()}
    result = InstallResult()
    for row in rows:
        src, dst = audio_dir / row["rel"], install_dir / row["rel"]
        if not src.is_file():
            result.errors.append(f"{row['id']}: Datei fehlt ({src})")
            continue
        if not _same_file(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            part = dst.with_name(f"{dst.stem}.part.ogg")
            shutil.copy2(src, part)
            replace_with_retry(part, dst)
            result.copied += 1
        entries[row["id"]] = {"file": row["rel"], "duration": round(float(row["duration"]), 3)}
    variants: dict[str, list[str]] = {}
    for full_id in entries:
        base, variant = split_variant(full_id)
        if variant:
            variants.setdefault(base, []).append(variant)
    index = {"version": INDEX_VERSION, "language": language, "entries": entries,
             "variants": {b: sorted(v) for b, v in variants.items()}}
    install_dir.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_name("index.json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    replace_with_retry(tmp, index_path)
    result.entries = len(entries)
    return result
```

- [ ] **Step 4: `install` in `pipeline.py` verdrahten**

Import: `from drova_voice.install import install_audio`. Funktion vor `HANDLERS`:
```python
def _install(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    if not encoded:
        return _fail(f"{encoded_path(cfg)} fehlt oder ist leer (zuerst `drova-voice encode` ausführen)")
    wanted = {l.id for l in lines}
    rows = [r for i, r in encoded.items() if i in wanted]
    result = install_audio(rows, audio_dir(cfg), cfg.install_dir, cfg.language)
    print(f"{result.copied} Dateien kopiert, index.json mit {result.entries} Einträgen -> {cfg.install_dir}")
    for e in result.errors[:10]:
        print(f"FEHLER {e}", file=sys.stderr)
    return 1 if result.errors else 0
```
`HANDLERS`: `"install": _install,`. `add_parsers`:
```python
    ins = sub.add_parser("install", help="Dateien in den Mod-Ordner kopieren und index.json schreiben")
    ins.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht (frühere Einträge bleiben erhalten)")
```

- [ ] **Step 5: Vertrag für die Mod schreiben** (`docs/audio-format.md`)

```markdown
# Audioformat (Vertrag zwischen Generator und Mod)

Der Generator schreibt nach `<Spiel>/Mods/DrovaVoice/Audio/<Sprache>/`. Die Mod liest **nur** `index.json` und bildet keine Dateinamen selbst.

## Ordner

```
Audio/de/
├─ index.json
├─ dialog/<sha1(id)[:16]>.ogg      NPC-Dialog
├─ bark/…                          Welt-Kommentare (später)
├─ letter/…                        Briefe (später)
└─ player/default/…                Spielerzeilen (Auswahloptionen); weitere Sets später als player/<set>/
```

Dateien sind OGG Vorbis, mono, auf −16 LUFS angeglichen, Stille am Anfang und Ende entfernt.

## index.json

```json
{
  "version": 1,
  "language": "de",
  "entries": {
    "<treeName>|<locaPath>|<locaKey>":        {"file": "dialog/0123456789abcdef.ogg", "duration": 3.214},
    "<treeName>|<locaPath>|<locaKey>|c2":      {"file": "player/default/…ogg",          "duration": 1.9},
    "<treeName>|<locaPath>|<locaKey>#neutral": {"file": "dialog/…ogg",                   "duration": 2.0}
  },
  "variants": {"<treeName>|<locaPath>|<locaKey>": ["arden", "neutral"]}
}
```

- Schlüssel = volle Zeilen-ID nach Spec §4 (Aussage, Auswahloption mit `|c<index>`, optional `#<variante>`); Bildung wie in `DrovaVoice.Core.LineIds` (Testvektoren `tests/vectors/line_ids.json`).
- `file` ist relativ zum Sprachordner, mit `/`. `duration` in Sekunden (gerundet auf Millisekunden).
- `variants` listet je Basis-ID die vorhandenen Varianten; Zeilen ohne Variante stehen nicht darin. Fehlt die gewünschte Variante, gilt die Basis-ID.
- Zeilen ohne Eintrag bleiben stumm (Untertitel wie im Original). Es gibt keine Einträge für Zeilen mit `$GVAR:` im Text, bis die Namensvarianten gebaut sind.
- Der Generator ergänzt den Index bei jedem `install` (frühere Einträge bleiben, solange ihre Datei existiert).
```

- [ ] **Step 6: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün.

- [ ] **Step 7: Commit**

```bash
git add generator docs/audio-format.md
git commit -m "Add the install step and define the index.json contract for the mod"
```

---

### Task 7: `report` (Statusbericht)

**Files:**
- Create: `generator/drova_voice/report.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_report.py`, `generator/tests/test_pipeline_report.py`

**Interfaces:**
- Consumes: `lines.Line`, `synth.SKIP_NO_VOICE`, `casting.Casting`, synth rows (`ok`, `flagged`), encoded rows, index entries.
- Produces:
  - `report.build_report(lines, casting, synth_rows: Mapping[str, dict], encoded: Mapping[str, dict], index_entries: Mapping[str, dict]) -> dict[str, CategoryStatus]` mit `CategoryStatus.counts: Counter[str]` (Schlüssel: `installiert`, `kodiert`, `erzeugt`, `fehler`, `offen`, `übersprungen: <Grund>`) und `flagged: int`.
  - `report.format_report(statuses) -> str`.
  - Statusreihenfolge je Zeile: übersprungen (Zeilen-`skip`, sonst `no_voice`, wenn der Sprecher keine Stimme hat) → `installiert` (in Index) → `kodiert` → `erzeugt` (Synth ok) → `fehler` (Synth nicht ok) → `offen`.
  - `pipeline._report`.

- [ ] **Step 1: Failing Tests schreiben**

`generator/tests/test_report.py`:
```python
from drova_voice.casting import Casting
from drova_voice.lines import Line
from drova_voice.report import build_report, format_report

CASTING = Casting("leon", {"mira": "lena"})


def line(key, actor="Mira", category="dialog", skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw="x", speech="" if skip else "x", stage=(), skip=skip)


def test_statuses_follow_the_pipeline_order():
    lines = [line("Plh_1"), line("Plh_2"), line("Plh_3"), line("Plh_4"), line("Plh_5"), line("Plh_6", skip="gvar"),
             line("Plh_7", actor="Fremder"), line("Plh_8", actor="Player", category="player")]
    synth = {"T|P|Plh_1": {"ok": True, "flagged": False}, "T|P|Plh_2": {"ok": True, "flagged": True},
             "T|P|Plh_3": {"ok": True, "flagged": False}, "T|P|Plh_4": {"ok": False, "flagged": False}}
    encoded = {"T|P|Plh_1": {}, "T|P|Plh_2": {}}
    index = {"T|P|Plh_1": {}}
    report = build_report(lines, CASTING, synth, encoded, index)
    assert report["dialog"].counts == {"installiert": 1, "kodiert": 1, "erzeugt": 1, "fehler": 1, "offen": 1,
                                       "übersprungen: gvar": 1, "übersprungen: no_voice": 1}
    assert report["dialog"].flagged == 1
    assert report["player"].counts == {"offen": 1}


def test_format_report_lists_categories_and_totals():
    text = format_report(build_report([line("Plh_1"), line("Plh_2", skip="gvar")], CASTING, {}, {}, {}))
    assert "dialog" in text and "2 Zeilen" in text and "übersprungen: gvar: 1" in text and "offen: 1" in text
```

`generator/tests/test_pipeline_report.py`:
```python
import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


def test_report_right_after_extract(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    capsys.readouterr()
    assert main(base + ["report"]) == 0
    out = capsys.readouterr().out
    assert "offen: 2" in out and "übersprungen: gvar: 1" in out and "übersprungen: unspeakable: 1" in out


@needs_ffmpeg
def test_report_after_full_run(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    guarded(lambda: main(base + ["synth", "--engine", "fake"]))
    guarded(lambda: main(base + ["encode"]))
    main(base + ["install"])
    capsys.readouterr()
    assert main(base + ["report"]) == 0
    out = capsys.readouterr().out
    assert "dialog: 4 Zeilen -> installiert: 2" in out and "player: 1 Zeilen -> installiert: 1" in out
```
(Die Ausgabe hat je Kategorie eine Zeile: direkt nach `extract` steht `dialog` mit `offen: 2` und `player` mit `offen: 1`; nach dem vollen Lauf sind beide installiert.)

- [ ] **Step 2: Tests laufen lassen (müssen scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_report.py tests/test_pipeline_report.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.report`).

- [ ] **Step 3: `report.py` schreiben**

`generator/drova_voice/report.py`:
```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from drova_voice.casting import Casting
from drova_voice.lines import Line
from drova_voice.synth import SKIP_NO_VOICE

ORDER = ("installiert", "kodiert", "erzeugt", "fehler", "offen")


@dataclass
class CategoryStatus:
    counts: Counter = field(default_factory=Counter)
    flagged: int = 0

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _status(line: Line, casting: Casting, synth: Mapping[str, dict], encoded: Mapping[str, dict],
            index: Mapping[str, dict]) -> str:
    if line.skip:
        return f"übersprungen: {line.skip}"
    if casting.voice_for(line) is None:
        return f"übersprungen: {SKIP_NO_VOICE}"
    if line.id in index:
        return "installiert"
    if line.id in encoded:
        return "kodiert"
    row = synth.get(line.id)
    if row is not None:
        return "erzeugt" if row.get("ok") else "fehler"
    return "offen"


def build_report(lines: Sequence[Line], casting: Casting, synth_rows: Mapping[str, dict],
                 encoded: Mapping[str, dict], index_entries: Mapping[str, dict]) -> dict[str, CategoryStatus]:
    result: dict[str, CategoryStatus] = {}
    for line in lines:
        status = result.setdefault(line.category, CategoryStatus())
        status.counts[_status(line, casting, synth_rows, encoded, index_entries)] += 1
        row = synth_rows.get(line.id)
        if row and row.get("ok") and row.get("flagged"):
            status.flagged += 1
    return result


def format_report(statuses: Mapping[str, CategoryStatus]) -> str:
    out = []
    for category in sorted(statuses):
        st = statuses[category]
        parts = [f"{k}: {st.counts[k]}" for k in ORDER if st.counts[k]]
        parts += [f"{k}: {n}" for k, n in sorted(st.counts.items()) if k.startswith("übersprungen")]
        flag = f"; auffällige Dauer: {st.flagged}" if st.flagged else ""
        out.append(f"{category}: {st.total} Zeilen -> " + (", ".join(parts) or "-") + flag)
    return "\n".join(out) or "keine Zeilen"
```

- [ ] **Step 4: `report` in `pipeline.py` verdrahten**

Imports: `from drova_voice.report import build_report, format_report`, `import json` ist schon da. Funktion vor `HANDLERS`:
```python
def _report(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        _, casting = _load_casting(cfg)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    index_path = cfg.install_dir / "index.json"
    entries = {}
    if index_path.is_file():
        entries = json.loads(index_path.read_text(encoding="utf-8-sig")).get("entries", {})
    statuses = build_report(lines, casting, latest_by_id(read_jsonl_lenient(synth_results_path(cfg))),
                            latest_by_id(read_jsonl_lenient(encoded_path(cfg))), entries)
    print(format_report(statuses))
    return 0
```
`HANDLERS`: `"report": _report,`. `add_parsers`:
```python
    rp = sub.add_parser("report", help="Status je Kategorie: offen, erzeugt, kodiert, installiert, übersprungen")
    rp.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
```

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add generator
git commit -m "Add the report step: per-category status from extract to install"
```

---

### Task 8: `preview` (Hörseite für einen NPC)

**Files:**
- Create: `generator/drova_voice/preview.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_preview.py`

**Interfaces:**
- Consumes: `lines.Line`, encoded rows, `emotions.EmotionTag`, `pipeline.audio_dir/encoded_path`.
- Produces: `preview.write_preview(lines, encoded: Mapping[str, dict], emotions: Mapping[str, EmotionTag], audio_dir: Path, out_path: Path, title: str) -> Path` (eine HTML-Seite, Zeilen in Reihenfolge der Bäume/Knoten; je Zeile Sprecher, Emotion, Sprechtext, `<audio>`; nicht erzeugte Zeilen mit Grund), `pipeline._preview` (schreibt `out/preview/index.html`).

- [ ] **Step 1: Failing Test schreiben**

`generator/tests/test_preview.py`:
```python
from drova_voice.emotions import EmotionTag
from drova_voice.lines import Line
from drova_voice.preview import write_preview


def line(key, speech="Zum Brunnen <bitte> & los.", actor="Mira", skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category="dialog", generic=False, raw=speech, speech="" if skip else speech, stage=(), skip=skip)


def test_preview_escapes_text_and_links_audio(tmp_path):
    audio = tmp_path / "audio"
    (audio / "dialog").mkdir(parents=True)
    (audio / "dialog" / "a.ogg").write_bytes(b"x")
    page = write_preview([line("Plh_1"), line("Plh_2", skip="gvar"), line("Plh_3")],
                         {"T|P|Plh_1": {"id": "T|P|Plh_1", "rel": "dialog/a.ogg", "duration": 1.0, "key": "k"}},
                         {"T|P|Plh_1": EmotionTag("sad", 0.5, source="llm")}, audio, tmp_path / "out" / "index.html", "Test <NPC>")
    html = page.read_text(encoding="utf-8")
    assert "Zum Brunnen &lt;bitte&gt; &amp; los." in html and "<bitte>" not in html
    assert "Test &lt;NPC&gt;" in html
    assert html.count("<audio") == 1 and "a.ogg" in html
    assert "sad 0.5" in html
    assert "übersprungen: gvar" in html and "noch nicht erzeugt" in html
```

- [ ] **Step 2: Test laufen lassen (muss scheitern)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_preview.py -q`
Expected: FAIL (`ModuleNotFoundError: drova_voice.preview`).

- [ ] **Step 3: `preview.py` schreiben**

`generator/drova_voice/preview.py`:
```python
from __future__ import annotations

import html
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.emotions import EmotionTag
from drova_voice.lines import Line

_STYLE = ("body{font:15px system-ui;margin:2rem auto;max-width:60rem;padding:0 1rem}"
          "tr:nth-child(even){background:#8881}td{padding:.4rem .6rem;vertical-align:top}"
          ".who{white-space:nowrap;font-weight:600}.meta{color:#888;font-size:.85em}")


def write_preview(lines: Sequence[Line], encoded: Mapping[str, dict], emotions: Mapping[str, EmotionTag],
                  audio_dir: Path, out_path: Path, title: str) -> Path:
    esc = html.escape
    rows = []
    for line in lines:
        emo = emotions.get(line.id)
        meta = f"{emo.emotion} {emo.intensity:g}" if emo else "neutral"
        row = encoded.get(line.id)
        if line.skip:
            cell = f"<span class='meta'>übersprungen: {esc(line.skip)}</span>"
        elif row and (Path(audio_dir) / row["rel"]).is_file():
            cell = f'<audio controls preload="none" src="{esc((Path(audio_dir) / row["rel"]).resolve().as_uri())}"></audio>'
        else:
            cell = "<span class='meta'>noch nicht erzeugt</span>"
        text = line.speech or line.raw
        rows.append(f"<tr><td class='who'>{esc(line.actor)}<div class='meta'>{esc(meta)}</div></td>"
                    f"<td>{esc(text)}<div class='meta'>{esc(line.id)}</div></td><td>{cell}</td></tr>")
    page = (f"<!doctype html><meta charset='utf-8'><title>{esc(title)}</title><style>{_STYLE}</style>"
            f"<h1>{esc(title)}</h1><table>{''.join(rows)}</table>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path
```

- [ ] **Step 4: `preview` in `pipeline.py` verdrahten**

Import: `from drova_voice.preview import write_preview`. Funktion vor `HANDLERS`:
```python
def _preview(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        emotions = read_emotions(emotions_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    page = write_preview(lines, latest_by_id(read_jsonl_lenient(encoded_path(cfg))), emotions, audio_dir(cfg),
                         cfg.out_dir / "preview" / "index.html", f"Hörprobe {args.npc or 'alle Zeilen'}")
    print(f"Hörseite: {page}")
    return 0
```
`HANDLERS`: `"preview": _preview,`. `add_parsers`:
```python
    pv = sub.add_parser("preview", help="Hörseite out/preview/index.html (Zeilen mit Emotion und Audio)")
    pv.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")
```

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests -q`
Expected: alle grün.

- [ ] **Step 6: Commit**

```bash
git add generator
git commit -m "Add the preview step: a listening page per NPC"
```

---

### Task 9: Durchlauf mit Fake-Engine, Bedienungsdoku und echter Durchstich für Adela

**Files:**
- Create: `generator/tests/test_pipeline_e2e.py`, `docs/generator.md`, `docs/decisions/2026-10-adela-durchstich.md`
- Modify: `casting/casting.yaml` (nach dem Hörtest), `casting/emotions.jsonl` (LLM-Zeilen für Adela)

**Interfaces:**
- Consumes: alle Unterbefehle aus Task 1-8.
- Produces: einen grünen End-zu-Ende-Test, die Bedienungsanleitung und `<Spiel>/Mods/DrovaVoice/Audio/de/` mit Adelas Dateien und `index.json` als Eingabe für Plan 4.

- [ ] **Step 1: End-zu-Ende-Test schreiben** (`generator/tests/test_pipeline_e2e.py`)

```python
import json
import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


@needs_ffmpeg
def test_whole_pipeline_with_fake_engine(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    steps = [["extract"], ["cast", "--check", "--npc", "Mira"], ["emote", "--npc", "Mira"],
             ["synth", "--engine", "fake", "--workers", "2", "--npc", "Mira"], ["encode", "--npc", "Mira"],
             ["install", "--npc", "Mira"], ["report", "--npc", "Mira"], ["preview", "--npc", "Mira"]]
    for step in steps:
        assert guarded(lambda s=step: main(base + s)) == 0, step
    out = capsys.readouterr().out
    assert "dialog: 4 Zeilen" in out and "installiert: 2" in out and "player: 1 Zeilen" in out
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index["entries"]) == 3
    assert (pipeline_repo.repo / "out" / "preview" / "index.html").is_file()
    # zweiter Durchlauf: alles kommt aus Cache bzw. Stempeln, der Index bleibt gleich
    for step in steps[3:]:
        assert guarded(lambda s=step: main(base + s)) == 0, step
    assert json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8")) == index
```
Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_pipeline_e2e.py -q`
Expected: PASS (alle Schritte sind aus den Tasks 1-8 vorhanden). Schlägt es fehl, ist die Verdrahtung in `pipeline.py` unvollständig (fehlender `HANDLERS`-Eintrag oder Parser): dort beheben, nicht im Test.

- [ ] **Step 2: Bedienungsdoku schreiben** (`docs/generator.md`)

Inhalt (Abschnitte, jeweils mit den echten Befehlen aus Task 1-8):
1. Voraussetzungen (`generator/.venv`, `config.yaml`, ffmpeg, `FISH_API_KEY` als Umgebungsvariable, Export liegt unter `data/export/de/manifest.json`; wer nur `manifest-loaded.json` hat, kopiert oder übergibt `extract --manifest <Pfad>`).
2. Reihenfolge `extract → cast --check → emote → synth → encode → install → report → preview`, jeweils mit `--npc <Name>`.
3. Wo was liegt (`data/lines.jsonl`, `data/synth/results.jsonl`, `data/encoded.jsonl`, `cache/synth/`, `out/audio/<Sprache>/`, Mod-Ordner) und was man löschen darf (alles außer `casting/`).
4. Wiederaufnehmen und Neu-Erzeugen (Cache-Schlüssel enthält Text, Stimme, Modell, Cues: geänderter Text oder Stimme erzeugt automatisch neu; zum Erzwingen die WAV in `cache/synth/` löschen).
5. Grenzen von Plan 3: Zeilen mit `$GVAR:` werden übersprungen, Spielerstimme nur `default`, keine Varianten, keine Barks/Briefe, Stimmenzuordnung vorläufig.
Kein Spielertext in der Doku.

- [ ] **Step 3: Commit (Tests und Doku)**

```bash
git add generator/tests/test_pipeline_e2e.py docs/generator.md
git commit -m "Add the end-to-end pipeline test and the generator guide"
```

- [ ] **Step 4: Freigabe für den echten Lauf einholen (Hauptsitzung, nicht Subagent)**

Vorlegen und auf ein klares „ja" warten: Es werden die **22 echten Zeilen der vier Adela-Bäume** (15 Adela, 7 Spieler-Auswahloptionen) als Text an `api.fish.audio` gesendet (Stimmen vorläufig `melanie` für Adela und `leon` für den Spieler, Modell `s2.1-pro-free`) und zusätzlich an einen Haiku-Subagenten (Emotionen, siehe Step 6). Außerdem wird nach `<Spiel>/Mods/DrovaVoice/Audio/de/` geschrieben (Mod-Ordner, keine Downloads). Der Fish-Schlüssel kommt aus `FISH_API_KEY` in der Shell des Nutzers; ein im Chat gezeigter Schlüssel ist danach zurückzusetzen.

- [ ] **Step 5: Extract, Prüfen, Regie-Emotionen**

Run (Bash, in `generator/`):
```bash
.venv/Scripts/drova-voice extract --manifest ../data/export/de/manifest-loaded.json
.venv/Scripts/drova-voice cast --check --npc Adela
.venv/Scripts/drova-voice emote --npc Adela
```
Expected: `19535 Zeilen -> …\data\lines.jsonl; übersprungen: …`; `Stimmen (Zeilen): melanie: 15, leon: 7` und `Sprecher ohne Stimme: keine`; `N Emotionen -> …` (N = Zahl der Adela-Zeilen mit Regieanweisung, kann 0 sein).
Abweichung bei `cast --check` (z. B. ein weiterer Sprecher in den Bäumen): Sprecher in `casting/casting.yaml` ergänzen und den Nutzer fragen, welche Stimme.

- [ ] **Step 6: LLM-Emotionen für Adela (Haiku-Subagent, mit Ja aus Step 4)**

Zeilen für den Subagenten ausgeben (Hauptsitzung, nur Adelas Bäume):
```bash
.venv/Scripts/python.exe -I - <<'EOF'
from drova_voice.lines import read_lines, select_npc
for l in select_npc(read_lines("../data/lines.jsonl"), "Adela"):
    print(f"{l.id}\t{l.actor}\t{l.speech or '(übersprungen: ' + str(l.skip) + ')'}")
EOF
```
Subagent-Auftrag (Modell haiku, nur lesend und eine Ausgabedatei im Scratchpad): „Du bekommst die Zeilen von vier Dialogbäumen (ID, Sprecher, Text). Gib je Zeile, bei der eine Emotion klar im Text steht, genau eine JSON-Zeile aus: `{"id": "<ID>", "emotion": "<neutral|angry|contemplative|excited|joyful|mundane|nervous|sad|stern|surprised|tender>", "intensity": <0.0-1.0>, "events": [], "emphasis": [], "notes": [], "source": "llm"}`. Regeln: Zurückhaltung; Standard ist neutral/mundane und diese Zeilen **nicht** ausgeben; `events` bleiben leer, außer der Text nennt den Laut ausdrücklich; höchstens ein Wort in `emphasis`. Keine Texte wiederholen, nur JSON-Zeilen.“ Die Zeilen werden in `casting/emotions.jsonl` eingefügt (Hauptsitzung prüft, dass nur IDs aus Adelas Bäumen vorkommen), danach `emote --npc Adela` erneut ausführen: die `llm`-Zeilen bleiben erhalten.

- [ ] **Step 7: Erzeugen, kodieren, installieren**

Run (Bash, in `generator/`; `FISH_API_KEY` ist in der Umgebung gesetzt, nicht in der Befehlszeile):
```bash
.venv/Scripts/drova-voice synth --npc Adela --workers 4
.venv/Scripts/drova-voice encode --npc Adela
.venv/Scripts/drova-voice install --npc Adela
.venv/Scripts/drova-voice report --npc Adela
.venv/Scripts/drova-voice preview --npc Adela
```
Expected: `22 erzeugt (0 aus dem Cache, 22 neu erzeugt), 0 Fehler, 0 auffällige Dauer; übersprungen: keine` (Abweichungen nennen); `22 kodiert`; `N Dateien kopiert, index.json mit 22 Einträgen`; Bericht `dialog: 15 Zeilen -> installiert: 15` und `player: 7 Zeilen -> installiert: 7`; `Hörseite: …\out\preview\index.html`. Bei `AUFFÄLLIG`-Zeilen die Hörseite abhören, ob sie tatsächlich falsch klingen (Halluzination, abgeschnitten); falls ja, WAV in `cache/synth/` löschen und `synth` wiederholen.

- [ ] **Step 8: Hörtest durch den Nutzer**

Hörseite mit `SendUserFile`/Browser öffnen (`out/preview/index.html`). Der Nutzer hört Adela und die Spielerzeilen ab und entscheidet: Stimmen passend (sonst in `casting/casting.yaml` ändern, `synth --npc Adela` wiederholen, ändert sich automatisch), Emotionen passend, Lautstärke unter den Zeilen gleichmäßig, Zeilen mit Artefakten. Die Entscheidungen kommen in `docs/decisions/2026-10-adela-durchstich.md` (nur IDs/Zahlen/Stimmennamen, keine Spieltexte): Datum, Stimmen für Adela und Spieler, Auffälligkeiten, Zeitbedarf, Befunde für den Vollauf (M4), offene Fragen für Plan 4.

- [ ] **Step 9: Commit**

```bash
git add casting docs/decisions/2026-10-adela-durchstich.md
git commit -m "Record the Adela vertical slice: casting, emotions and listening results"
```
Abschluss: `<Spiel>/Mods/DrovaVoice/Audio/de/index.json` mit 22 Einträgen liegt bereit; Plan 4 (Wiedergabe in der Mod, M3) schreibt der Nutzer mit mir als Nächstes, Grundlage ist `docs/audio-format.md`.

---

## Self-Review (vom Plan-Autor)

- **Spec-Abdeckung (§6):** `extract` (Task 1; Briefe und `skip_runtime` bewusst später), `cast` (Task 2; Dossiers und LLM-Casting später, Zuordnung per Datei), `emote` (Task 3, §7 Regieanweisungen und LLM-Zeilen), `synth` (Task 4: Cache-Schlüssel, Fortsetzen, Plausibilität mit 2 Wiederholungen, Parallelität), `encode` (Task 5: Stille trimmen, −16 LUFS, OGG mono, `*flüstert*` leiser; „gehaucht“ bewusst offen), `install` (Task 6, §4 Dateiablage und `index.json`), `report`/`preview` (Tasks 7-8). `names`, `dossier`, `regen` und Sonderbehandlung sehr kurzer Zeilen folgen im Vollauf-Plan (M4); kurze Zeilen werden hier nur mit Obergrenze geprüft und im Bericht markiert.
- **Platzhalter-Scan:** Alle Schritte enthalten Code oder genaue Befehle; Task 9 Step 2 beschreibt die Doku-Abschnitte (Inhalt hängt von den Befehlen ab, die oben vollständig stehen).
- **Typkonsistenz:** `Line` (Task 1) wird in Task 2-8 unverändert verwendet; `SynthResult.to_dict()` Felder (`id, key, wav, duration, ok, attempts, flagged, error`) entsprechen den Zugriffen in Task 5 (`row["wav"]`, `row["key"]`, `row.get("ok")`) und Task 7 (`ok`, `flagged`); `run_encode`-Zeilen (`id, rel, duration, key`) entsprechen Task 6 (`row["rel"]`, `row["duration"]`) und Task 8; Pfadhelfer `synth_results_path/encoded_path/audio_dir/emotions_path` stehen in `pipeline.py` vor ihrer Verwendung (Tasks 3-5).
- **Review Focus:** `$GVAR` (Task 1 Test `test_gvar_lines_are_skipped_not_spoken`), nicht sprechbar (Task 1 + `test_build_jobs_skips_and_maps_voices`), Abbruch/Wiederaufnahme (Task 4 `test_stale_part_file…`, `test_dead_worker…`, Task 1 `test_lenient_skips_truncated_last_line…`), ID-Abweichung und Duplikate (Task 1), unbekannte Stimme (Task 2), zweiter Install und Umlaute (Task 6), ffmpeg fehlt (Task 5 `test_find_tools_reports_missing_ffmpeg`).
