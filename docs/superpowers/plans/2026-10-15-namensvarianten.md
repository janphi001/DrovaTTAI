# Namensvarianten (neutral) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NPC-Zeilen mit dem Spielernamen (`$GVAR:EVars_Player.Name$`) werden in einer neutralen Fassung ohne Namen vertont (ID `<Basis-ID>#neutral`) und von der Mod bevorzugt abgespielt.

**Architecture:** `build_lines` ersetzt für Zeilen, deren einziger Platzhalter der Spielername ist, den Sprechtext durch `make_name_variants(...).neutral` und hängt `#neutral` an die ID; `synth`, `encode`, `install` und der Index kennen Varianten schon. Zeilen ohne neutrale Fassung und Zeilen mit Quest-/Geldwerten bleiben stumm (`gvar_name`, `gvar_value`). Die Mod schlägt in `VoiceService.GetClip` zuerst `<id>#neutral` nach, sonst `<id>`.

**Tech Stack:** Python 3.12 (`generator/.venv`), pytest, C# (net8.0 Core-Bibliothek, xUnit), MelonLoader-Mod.

**Spec:** `docs/superpowers/specs/2026-10-15-namensvarianten-design.md` (Vertrag: `docs/audio-format.md`).

## Global Constraints

- Generator-Befehle im Ordner `generator/` (Git Bash: `.venv/Scripts/python.exe -m pytest -q`, `.venv/Scripts/drova-voice ...`). Ausgangsstand: 471 pytest und 151 xUnit grün.
- C#-Tests: `dotnet test mod/DrovaVoice.Core.Tests -v q` (im Repo-Wurzelordner).
- Meldungen, Kommentare und Dokumente auf Deutsch; Commits englisch, Imperativ, **ohne** `Co-Authored-By`- oder sonstige Claude-Zeile; nichts pushen oder mergen.
- **Keine echten Drova-Dialogtexte ins Git** (Tests mit erfundenem Text). `data/`, `cache/`, `out/` sind per `.gitignore` ausgeschlossen.
- **Texte gehen nur nach ausdrücklichem Ja des Nutzers an Fish.** Der Key (`FISH_API_KEY`) kommt vom Nutzer im Chat und steht nur als Umgebungsvariable im Einzelbefehl, nie in Dateien.
- `dotnet build mod/DrovaVoice -c Release` kopiert in den Spielordner: nur bei geschlossenem Spiel und nur in Task 5.
- Downloads und Installationen nur nach Rückfrage; alles auf Laufwerk D:.

## Review Focus

- Name steht mitten im Satz („Komm mit NAME zum Brunnen.“): keine neutrale Fassung, Zeile bleibt stumm (`gvar_name`), kein Absturz (Task 1).
- Zeile mit Name **und** Quest-Wert: zählt als `gvar_value`, nie als neutral (Task 1).
- Zeile besteht nur aus Name (und Regieanweisung), z. B. „*seufzt* NAME!“: keine neutrale Fassung, stumm als `gvar_name` (Task 1).
- Ein später nicht mehr installierter `#neutral`-Eintrag verschwindet beim nächsten `install` aus dem Index (Task 2).
- Auswahloptionen und Zeilen ohne Variante spielen weiter mit der Basis-ID (Task 3).

---

## File Structure

- `generator/drova_voice/player_name.py` (ändern): Konstante `NAME_VAR`.
- `generator/drova_voice/lines.py` (ändern): Klassifizierung der `$GVAR`-Zeilen, neutrale Fassung, ID mit Variante.
- `generator/drova_voice/install.py` (ändern): Bereinigung entfernt auch Einträge, deren volle ID in `drop_ids` steht.
- `generator/tests/test_lines.py`, `test_install.py`, `conftest.py`, `test_pipeline_extract.py`, `test_pipeline_report.py`, `test_pipeline_synth.py`, neu `test_pipeline_neutral.py` (Tests).
- `mod/DrovaVoice.Core/LineIds.cs` (ändern): Konstante `NeutralVariant`.
- `mod/DrovaVoice.Core/AudioIndex.cs` (ändern): `ResolveVariant`.
- `mod/DrovaVoice/Playback/VoiceService.cs` (ändern): `GetClip` nutzt `ResolveVariant`.
- `mod/DrovaVoice.Core.Tests/AudioIndexTests.cs` (ändern).
- `docs/audio-format.md`, `docs/playback.md`, `docs/generator.md`, `docs/HANDOFF.md` (ändern).

---

### Task 1: Zeilen mit Spielernamen klassifizieren und neutral machen

**Files:**
- Modify: `generator/drova_voice/player_name.py`
- Modify: `generator/drova_voice/lines.py`
- Modify: `generator/tests/test_lines.py`, `generator/tests/conftest.py`, `generator/tests/test_pipeline_extract.py`, `generator/tests/test_pipeline_report.py`, `generator/tests/test_pipeline_synth.py`

**Interfaces:**
- Consumes: `make_name_variants(text) -> NameVariants` (`.neutral: str | None`), `with_variant(line_id, variant)` aus `ids.py`, `GVAR_RE` aus `speech_text.py`.
- Produces: `lines.SKIP_GVAR_NAME = "gvar_name"`, `lines.SKIP_GVAR_VALUE = "gvar_value"` (ersetzen `SKIP_GVAR`); `player_name.NAME_VAR = "EVars_Player.Name"`; `build_lines` liefert für Namenszeilen mit neutraler Fassung `Line(id="<Basis-ID>#neutral", speech=<neutraler Sprechtext>, raw=<Originaltext>, skip=None)`.

- [ ] **Step 1: Failing Tests schreiben**

In `generator/tests/test_lines.py` den Import ersetzen:

```python
from drova_voice.lines import (SKIP_GVAR_NAME, SKIP_GVAR_VALUE, SKIP_ID_MISMATCH, SKIP_PLAYER_CHOICE, SKIP_UNSPEAKABLE, Line,
                               build_lines, load_lexicon, load_loc_texts, read_lines, select_npc, write_lines)
```

und den Test `test_gvar_lines_are_skipped_not_spoken` (Zeilen 41-43) ersetzen durch:

```python
NAME = "$GVAR:EVars_Player.Name$"


def test_name_line_becomes_a_neutral_variant():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"Hallo {NAME}!"})
    assert line.id == statement_id(TREE, PATH, "Plh_1") + "#neutral"
    assert line.speech == "Hallo!" and line.raw == f"Hallo {NAME}!" and line.skip is None


def test_name_line_keeps_stage_directions_in_the_neutral_variant():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"*lacht* Hallo {NAME}!"})
    assert line.speech == "Hallo!" and line.stage[0]["text"] == "lacht" and line.id.endswith("#neutral")


def test_name_line_without_neutral_version_is_skipped_as_gvar_name():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"Komm mit {NAME} zum Brunnen."})
    assert line.skip == SKIP_GVAR_NAME and line.speech == "" and line.id == statement_id(TREE, PATH, "Plh_1")


def test_name_line_with_only_the_name_is_skipped_as_gvar_name():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"*seufzt* {NAME}!"})
    assert line.skip == SKIP_GVAR_NAME and line.speech == ""


def test_name_after_a_comma_is_dropped_in_the_neutral_variant():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"*grinst* Danke, {NAME}."})
    assert line.skip is None and line.speech == "Danke." and line.id.endswith("#neutral")


def test_value_placeholder_is_skipped_as_gvar_value():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen."})
    assert line.skip == SKIP_GVAR_VALUE and line.speech == ""


def test_name_together_with_a_value_is_skipped_as_gvar_value():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"Hallo {NAME}, das kostet $GVAR:A.B$ Münzen."})
    assert line.skip == SKIP_GVAR_VALUE and not line.id.endswith("#neutral")


def test_neutral_duplicate_ids_still_keep_the_first():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_1", text="Zweite Fassung.")), {(PATH, "Plh_1"): f"Hallo {NAME}!"})
    assert len(lines) == 1 and lines[0].id.endswith("#neutral")
```

In `generator/tests/conftest.py` Zeile `"Plh_4 { Hallo $GVAR:EVars_Player.Name$! }\n"` ersetzen durch (damit die Pipeline-Fixture eine stumme Zeile behält):

```python
    "Plh_4 { Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen. }\n"
```

In `generator/tests/test_pipeline_extract.py`: `"gvar"` → `"gvar_value"` in der Liste (Zeile 8) und `"gvar: 1"` → `"gvar_value: 1"` (Zeile 11). In `test_pipeline_report.py`: `"übersprungen: gvar: 1"` → `"übersprungen: gvar_value: 1"`. In `test_pipeline_synth.py`: `"übersprungen: gvar: 1, player_choice: 1, unspeakable: 1"` → `"übersprungen: gvar_value: 1, player_choice: 1, unspeakable: 1"`.

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_lines.py -q`
Expected: FAIL (ImportError `SKIP_GVAR_NAME`).

- [ ] **Step 3: Implementieren**

In `generator/drova_voice/player_name.py` unter `DEFAULT_NAME` ergänzen:

```python
NAME_VAR = "EVars_Player.Name"
```

In `generator/drova_voice/lines.py`: Imports ergänzen

```python
from drova_voice.ids import choice_id, normalize_loca_path, statement_id, with_variant
from drova_voice.player_name import NAME_VAR, make_name_variants
from drova_voice.speech_text import GVAR_RE, build_speech_text
```

(statt der bisherigen `ids`- und `speech_text`-Imports), die Konstante

```python
SKIP_GVAR = "gvar"
```

ersetzen durch

```python
SKIP_GVAR_NAME = "gvar_name"    # nur der Spielername, aber keine neutrale Fassung ohne ihn
SKIP_GVAR_VALUE = "gvar_value"  # Quest- oder Geldwerte (oder Name zusammen mit Werten): nicht vorab vertonbar
NEUTRAL = "neutral"
```

und in `build_lines` den Schleifenkörper ab `speech, stage, skip = "", (), None` bis zum Ende der `Line(...)`-Erzeugung ersetzen sowie `valid_ids` auf Basis-IDs umstellen:

```python
        speech, stage, skip = "", (), None
        out_id = line_id
        if not id_ok:
            skip = SKIP_ID_MISMATCH
        elif row.get("nodeType") == "choice":
            skip = SKIP_PLAYER_CHOICE
        elif "$GVAR:" in raw:
            if set(GVAR_RE.findall(raw)) != {NAME_VAR}:
                skip = SKIP_GVAR_VALUE
            else:
                neutral = make_name_variants(raw).neutral
                st = build_speech_text(neutral, None, lexicon) if neutral is not None else None
                if neutral is None:
                    skip = SKIP_GVAR_NAME
                elif st.is_speakable:
                    speech, stage = st.text, tuple({"text": s.text, "pos": s.pos} for s in st.stage)
                    out_id = with_variant(line_id, NEUTRAL)
                else:
                    skip = SKIP_UNSPEAKABLE
        else:
            st = build_speech_text(raw, None, lexicon)
            if st.is_speakable:
                speech, stage = st.text, tuple({"text": s.text, "pos": s.pos} for s in st.stage)
            else:
                skip = SKIP_UNSPEAKABLE
        out.append((line_id, Line(
            id=out_id, tree=row["tree"], loca_path=path, loca_key=row["locaKey"], node_type=row["nodeType"],
            choice_index=row.get("choiceIndex"), actor=row.get("actorName") or "", category=row.get("category") or "dialog",
            generic=bool(row.get("generic")), raw=raw, speech=speech, stage=stage, skip=skip,
        )))
    valid_ids = {base for base, l in out if l.skip != SKIP_ID_MISMATCH}
    return [l for base, l in out if not (l.skip == SKIP_ID_MISMATCH and base in valid_ids)]  # gültige Zeile geht vor
```

Außerdem die Zeile `out: list[Line] = []` in `out: list[tuple[str, Line]] = []` ändern (Paare aus Basis-ID und Zeile).

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python.exe -m pytest -q`
Expected: alle grün (471 + 8 neue). Schlägt ein anderer Test wegen `gvar` fehl, nur dessen erwartete Zeichenkette auf `gvar_value` bzw. `gvar_name` anpassen, nichts sonst.

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/player_name.py generator/drova_voice/lines.py generator/tests
git commit -m "Speak player-name lines in a neutral variant and split the gvar skip reason"
```

---

### Task 2: Install entfernt veraltete Varianten, Pipeline-Test für die neutrale Zeile

**Files:**
- Modify: `generator/drova_voice/install.py` (Zeile mit `drop_ids`-Filter)
- Modify: `generator/tests/test_install.py`
- Create: `generator/tests/test_pipeline_neutral.py`

**Interfaces:**
- Consumes: `install_audio(rows, audio_dir, install_dir, language, drop_ids)`, `split_variant`; `build_lines` aus Task 1.
- Produces: `install_audio` entfernt einen Eintrag, wenn seine volle ID **oder** seine Basis-ID in `drop_ids` steht.

- [ ] **Step 1: Failing Tests schreiben**

An `generator/tests/test_install.py` anhängen:

```python
def test_drop_ids_with_a_variant_id_remove_exactly_that_entry(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/bbbb.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg"), row("T|P|Plh_2#neutral", "dialog/bbbb.ogg")], audio, target, "de")
    install_audio([], audio, target, "de", drop_ids={"T|P|Plh_2#neutral"})
    index = read_index(target)
    assert sorted(index["entries"]) == ["T|P|Plh_1"] and index["variants"] == {}
```

`generator/tests/test_pipeline_neutral.py` neu:

```python
import json
import shutil

import pytest

from drova_voice.cli import main
from drova_voice.lines import read_lines

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")
NEUTRAL_ID = "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_4#neutral"


def _use_name_line(pipeline_repo):
    loc = pipeline_repo.game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog" / "NPC_Mira_de.loc"
    text = loc.read_text(encoding="utf-8")
    loc.write_text(text.replace("Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen.", "Hallo $GVAR:EVars_Player.Name$!"),
                   encoding="utf-8")


def test_extract_gives_the_name_line_a_neutral_id(pipeline_repo):
    _use_name_line(pipeline_repo)
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    line = next(l for l in read_lines(pipeline_repo.data / "lines.jsonl") if l.id == NEUTRAL_ID)
    assert line.speech == "Hallo!" and line.skip is None


@needs_ffmpeg
def test_neutral_line_is_installed_with_a_variants_block(pipeline_repo, guarded):
    _use_name_line(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (["extract"], ["synth", "--engine", "fake", "--workers", "2"], ["encode"], ["install"]):
        assert guarded(lambda s=step: main(base + s)) == 0, step
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert NEUTRAL_ID in index["entries"]
    assert index["variants"] == {"DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_4": ["neutral"]}


@needs_ffmpeg
def test_neutral_entry_disappears_when_the_speaker_loses_the_voice(pipeline_repo, guarded):
    _use_name_line(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (["extract"], ["synth", "--engine", "fake"], ["encode"], ["install"]):
        guarded(lambda s=step: main(base + s))
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    assert main(base + ["install"]) == 0
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert NEUTRAL_ID not in index["entries"] and index["variants"] == {}
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python.exe -m pytest tests/test_install.py tests/test_pipeline_neutral.py -q`
Expected: `test_drop_ids_with_a_variant_id_...` und `test_neutral_entry_disappears_...` schlagen fehl (Eintrag bleibt stehen); ohne ffmpeg werden die `needs_ffmpeg`-Tests übersprungen (dann `where ffmpeg` prüfen, ffmpeg ist für den Vollauf ohnehin nötig).

- [ ] **Step 3: Implementieren**

In `generator/drova_voice/install.py` die Zeile

```python
    entries = {i: e for i, e in entries.items() if split_variant(i)[0] not in drop_ids}
```

ersetzen durch

```python
    entries = {i: e for i, e in entries.items() if i not in drop_ids and split_variant(i)[0] not in drop_ids}
```

Der Kommentar darüber bekommt den Zusatz: „(Basis-ID entfernt alle Varianten, eine Varianten-ID nur diese)“.

- [ ] **Step 4: Alle Tests**

Run: `cd generator && .venv/Scripts/python.exe -m pytest -q`
Expected: alles grün.

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/install.py generator/tests
git commit -m "Drop stale variant entries on install and cover the neutral line end to end"
```

---

### Task 3: Mod bevorzugt `#neutral`

**Files:**
- Modify: `mod/DrovaVoice.Core/LineIds.cs`
- Modify: `mod/DrovaVoice.Core/AudioIndex.cs`
- Modify: `mod/DrovaVoice/Playback/VoiceService.cs`
- Modify: `mod/DrovaVoice.Core.Tests/AudioIndexTests.cs`

**Interfaces:**
- Consumes: `LineIds.WithVariant(string lineId, string? variant)`.
- Produces: `LineIds.NeutralVariant = "neutral"`; `AudioIndex.ResolveVariant(string? id, string variant) -> string?` (liefert `<id>#<variant>`, falls der Index diesen Eintrag hat, sonst `id` unverändert).

- [ ] **Step 1: Failing Tests schreiben**

In `mod/DrovaVoice.Core.Tests/AudioIndexTests.cs` in die Klasse einfügen (am Ende vor der schließenden Klammer):

```csharp
        private const string WithNeutral = @"{
  ""version"": 1, ""language"": ""de"",
  ""entries"": {
    ""DT_X|Dialog/A|Plh_1#neutral"": {""file"": ""dialog/0123456789abcdef.ogg"", ""duration"": 1.0},
    ""DT_X|Dialog/A|Plh_2"":         {""file"": ""dialog/fedcba9876543210.ogg"", ""duration"": 2.0}
  },
  ""variants"": {""DT_X|Dialog/A|Plh_1"": [""neutral""]}
}";

        [Fact]
        public void ResolveVariantPrefersTheVariantEntry()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.Equal("DT_X|Dialog/A|Plh_1#neutral", index.ResolveVariant("DT_X|Dialog/A|Plh_1", LineIds.NeutralVariant));
        }

        [Fact]
        public void ResolveVariantKeepsTheBaseIdWithoutVariantEntry()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.Equal("DT_X|Dialog/A|Plh_2", index.ResolveVariant("DT_X|Dialog/A|Plh_2", LineIds.NeutralVariant));
            Assert.Equal("DT_X|Dialog/A|Plh_9", index.ResolveVariant("DT_X|Dialog/A|Plh_9", LineIds.NeutralVariant));
            Assert.Equal("DT_X|Dialog/A|Plh_2|c0", index.ResolveVariant("DT_X|Dialog/A|Plh_2|c0", LineIds.NeutralVariant));
        }

        [Fact]
        public void ResolveVariantPassesNullAndEmptyThrough()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.Null(index.ResolveVariant(null, LineIds.NeutralVariant));
            Assert.Equal("", index.ResolveVariant("", LineIds.NeutralVariant));
        }

        [Fact]
        public void VariantEntriesAreNotCountedAsChoiceFallbacks()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.False(index.TryGetUniqueChoice("DT_X|Dialog/A|Plh_1", out _, out _));
        }
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `dotnet test mod/DrovaVoice.Core.Tests -v q`
Expected: Build-Fehler (`NeutralVariant`/`ResolveVariant` unbekannt).

- [ ] **Step 3: Implementieren**

In `mod/DrovaVoice.Core/LineIds.cs` unter `VariantSeparator`:

```csharp
        public const string NeutralVariant = "neutral";
```

In `mod/DrovaVoice.Core/AudioIndex.cs` nach `TryGet`:

```csharp
        /// <summary>
        /// Liefert <c>id#variant</c>, wenn der Index diese Variante hat, sonst <paramref name="id"/> unverändert
        /// (leere oder fehlende IDs gehen durch). So spielt die Mod bei Zeilen mit Spielernamen die neutrale Fassung.
        /// </summary>
        public string? ResolveVariant(string? id, string variant)
        {
            if (string.IsNullOrEmpty(id)) return id;
            string withVariant = LineIds.WithVariant(id!, variant);
            return _entries.ContainsKey(withVariant) ? withVariant : id;
        }
```

In `mod/DrovaVoice/Playback/VoiceService.cs` in `GetClip` die ersten Zeilen ersetzen:

```csharp
        public AudioClip? GetClip(string? id)
        {
            id = _index.ResolveVariant(id, LineIds.NeutralVariant);
            if (string.IsNullOrEmpty(id)) return null;
```

(der Rest der Methode bleibt; `id` ist danach die aufgelöste ID für Cache, Fehlerliste und Logs).

- [ ] **Step 4: Tests**

Run: `dotnet test mod/DrovaVoice.Core.Tests -v q`
Expected: 155 bestanden (151 + 4). Außerdem `dotnet build mod/DrovaVoice -c Release -p:... ` **nicht** ausführen (kopiert ins Spiel); zum reinen Kompilieren: `dotnet build mod/DrovaVoice.Core -c Release`.

- [ ] **Step 5: Commit**

```bash
git add mod
git commit -m "Prefer the neutral variant entry when the mod looks up a line"
```

---

### Task 4: Dokumentation

**Files:**
- Modify: `docs/audio-format.md` (Zeile „Es gibt keine Einträge für Zeilen mit `$GVAR:`…“)
- Modify: `docs/playback.md` (Zeilen 13, 50, 59)
- Modify: `docs/generator.md` (Zeile 62)
- Modify: `docs/HANDOFF.md`

- [ ] **Step 1: audio-format.md**

Die Zeile „Zeilen ohne Eintrag bleiben stumm … bis die Namensvarianten gebaut sind.“ ersetzen durch:

```
- Zeilen ohne Eintrag bleiben stumm (Untertitel wie im Original). Zeilen, deren einziger Platzhalter der Spielername (`$GVAR:EVars_Player.Name$`) ist, haben, wenn sich der Name sauber streichen lässt, nur den Eintrag `<Basis-ID>#neutral` (Text ohne den Namen); die Mod spielt diese Variante bevorzugt. Zeilen mit Quest- oder Geldwerten bleiben stumm. `#arden` wird nicht erzeugt.
```

- [ ] **Step 2: playback.md**

Zeile 13: „(und Zeilen mit `$GVAR:`)“ ersetzen durch „(und Zeilen mit Quest- oder Geldwerten)“. Zeile 50: „Zeilen mit `$GVAR:` bleiben stumm.“ ersetzen durch „Zeilen mit Spielernamen sprechen die neutrale Fassung (ohne Namen), Zeilen mit Quest-Werten bleiben stumm.“ Zeile 59: „Namensvarianten (`#arden`/`#neutral`) und Spielerstimm-Sets fehlen noch; es gilt die Basis-ID.“ ersetzen durch „Spielerstimm-Sets fehlen noch. Bei Zeilen mit Spielernamen gilt `…#neutral`, sonst die Basis-ID.“

- [ ] **Step 3: generator.md**

Zeile 62 ersetzen durch:

```
- Zeilen mit `$GVAR:` im Text: Ist der Spielername der einzige Platzhalter und lässt er sich streichen (`player_name.py`), wird die Zeile in neutraler Fassung vertont (ID `…#neutral`). Sonst übersprungen und im Bericht gezählt: `gvar_name` (Name steht mitten im Satz), `gvar_value` (Quest- oder Geldwerte, auch zusammen mit dem Namen).
```

- [ ] **Step 4: HANDOFF.md**

Im Abschnitt „Offene Entscheidungen / nächste Schritte“ Punkt 2 (Mod-Ausbau) die Namensvarianten streichen („Namensvarianten … 535 `$GVAR`-Zeilen, bisher übersprungen“) und unter „Stand“ eine Zeile `| Namensvarianten | neutral, siehe docs/superpowers/specs/2026-10-15-namensvarianten-design.md; Stand je nach Task 5 |` ergänzen. In „Offene Lücken“ ergänzen: „150 `gvar_name`- und 150 `gvar_value`-Zeilen bleiben stumm.“

- [ ] **Step 5: Commit**

```bash
git add docs
git commit -m "Document the neutral name variants"
```

---

### Task 5: Echter Lauf (interaktiv, nur mit Nutzer)

**Files:** keine Codeänderung; Daten unter `data/`, `cache/`, `out/` (nicht im Git).

- [ ] **Step 1: Zeilen neu extrahieren (lokal, kostet nichts)**

Run: `cd generator && .venv/Scripts/drova-voice extract`
Expected: Ausgabe nennt `gvar_name: ≈150`, `gvar_value: ≈150`, und die Zahl der Zeilen ohne `gvar_*` ist um die neutralen Namenszeilen (≈95) gewachsen. Abweichungen berichten, nicht beschönigen.

- [ ] **Step 2: Emotionen für die neuen IDs ergänzen (nur Regeln, lokal)**

Run: `cd generator && .venv/Scripts/drova-voice emote --help`, dann den Aufruf für Regeln ohne Subagent (wie in `docs/generator.md`) für alle Zeilen. Bestehende Einträge bleiben.

- [ ] **Step 3: Nutzer um das Ja für Fish bitten**

Dem Nutzer sagen: „≈95 neue Zeilen (≈N Zeichen) gehen an Fish; Rest kommt aus dem Cache.“ Zeichenzahl aus `drova-voice synth --dry-run` (falls vorhanden, sonst aus `data/lines.jsonl` die Summe der `speech`-Längen der Zeilen mit `#neutral`). **Ohne ausdrückliches Ja und ohne Key vom Nutzer nicht weitermachen.**

- [ ] **Step 4: Erzeugen, kodieren, installieren (nach Ja; Spiel geschlossen)**

Run (Key nur im Einzelbefehl): `cd generator && FISH_API_KEY=<vom Nutzer> .venv/Scripts/drova-voice synth --workers 8`, danach `.venv/Scripts/drova-voice encode` und `.venv/Scripts/drova-voice install`, dann `.venv/Scripts/drova-voice report`.
Expected: `synth` meldet nur die neuen Zeilen als „neu erzeugt“; `report` zeigt keine neuen Fehler; `index.json` enthält `variants` mit ≈95 Basis-IDs.

- [ ] **Step 5: Mod bauen (Spiel geschlossen)**

Run: `dotnet build mod/DrovaVoice -c Release`
Expected: Build ok, DLL im Spielordner aktualisiert.

- [ ] **Step 6: Hörtest durch den Nutzer**

Nutzer spricht im Spiel mit NPCs, die den Spieler beim Namen ansprechen (z. B. Begrüßungen). Erwartung: Stimme spricht die Zeile ohne Namen, Untertitel zeigen den Namen. Ergebnis im Handoff festhalten (HANDOFF.md „Stand“), committen.

```bash
git add docs/HANDOFF.md
git commit -m "Record the result of the neutral name variants run"
```

---

## Self-Review

- **Spec-Abdeckung:** Generator-Klassifizierung (Task 1), `#neutral`-ID und Index mit `variants` (Task 1/2, `install` schreibt `variants` bereits), Berichtskategorien `gvar_name`/`gvar_value` (Task 1; `extract`, `report`, `synth` geben `skip` allgemein aus), Fish-Verbrauch nur nach Ja (Task 5), Mod-Nachschlag (Task 3), Tests Python und C# (Tasks 1–3), Dokumentation (Task 4), Hörtest (Task 5).
- **Spec-Abweichung:** Die Spec nennt die Auswahl „in einer Core-Funktion“; das ist `AudioIndex.ResolveVariant` (Task 3).
- **Typen:** `SKIP_GVAR_NAME`/`SKIP_GVAR_VALUE`, `NAME_VAR`, `NEUTRAL`, `LineIds.NeutralVariant`, `AudioIndex.ResolveVariant` heißen in allen Tasks gleich.
- **Platzhalter:** keine offenen Stellen; Task 5 Step 2 verweist auf `emote --help` und `docs/generator.md`, weil die genauen Flags für den reinen Regel-Lauf vom Stand der CLI abhängen.
