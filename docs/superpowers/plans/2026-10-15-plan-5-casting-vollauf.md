# Plan 5: Casting und Vollauf Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle benannten Sprecher des Spiels bekommen eine passende Stimme (LLM-Steckbrief plus deterministische Zuteilung), Emotionen liegen für alle Zeilen vor, Varianten werden beim Kodieren angewendet und der Vollauf bei Fish läuft in Etappen mit sauberem Abbruch bei Limit- oder Guthabenfehlern.

**Architecture:** Neue kleine Module im Generator (`selection`, `profiles`, `assign`, `casting_sheet`) plus Erweiterungen von `fish_voices`, `casting`, `encode`, `synth`, `report`, `emote` und dünne Handler in `pipeline.py`. Claude-Subagents (Haiku) liefern nur Steckbriefe und Emotionen als JSONL, die der Generator prüft und importiert. Die Zuteilung der Stimmen ist ein deterministischer Greedy-Algorithmus; Ergebnis in `casting/casting_auto.yaml`, handgepflegte `casting/casting.yaml` gewinnt.

**Tech Stack:** Python 3.11, pytest, PyYAML, ffmpeg (libvorbis, rubberband), Fish Audio Cloud (nur nach Ja des Nutzers).

**Spec:** `docs/superpowers/specs/2026-10-15-plan-5-casting-vollauf-design.md` (dazu `docs/HANDOFF.md`).

## Global Constraints

- Alle Befehle für den Generator im Ordner `generator/` (Git Bash: `.venv/Scripts/python -m pytest -q`, `.venv/Scripts/drova-voice ...`). Ausgangsstand: 390 Tests grün (pytest), 151 xUnit.
- Meldungen, Kommentare und Dokumente auf Deutsch; Commits englisch, Imperativ, mit Zeile `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; nichts pushen oder mergen.
- **Keine echten Drova-Dialogtexte ins Git** (Tests mit erfundenem Text und erfundenen Sprechern). `data/`, `cache/`, `out/` sind per `.gitignore` ausgeschlossen; Eingabedateien für Subagents liegen unter `out/subagent/`.
- **Spieltexte gehen nur nach ausdrücklichem Ja des Nutzers in der Hauptsitzung an einen Dienst** (Fish, Haiku-Subagents). Je Etappe neu fragen. Der Fish-Key (`FISH_API_KEY`) kommt vom Nutzer im Chat und steht nur als Umgebungsvariable im Einzelbefehl, nie in Dateien.
- Sprecherschlüssel sind überall `actor.lower()`.
- Downloads und Installationen nur nach Rückfrage; alles auf Laufwerk D:.
- Der Mod-Ordner wird beim Installieren beschrieben; das Spiel muss dabei nicht laufen, aber Export/Mod-Bau sind nicht Teil dieses Plans.
- Nicht Teil von Plan 5: generische Sprecher (`NPC`, `Teacher`, `Druid`, `Actor`, `Participant`), Barks (`category == "bark"`), Briefe, Namensvarianten, Regler, 98-%-Lücke.
- Abweichung von der Spec (bewusst): Die 6 bereits besetzten Sprecher bekommen ihren Steckbrief wie alle anderen vom LLM; ihre Besetzung bleibt über `casting/casting.yaml` fest.

## Review Focus

Diese Fälle nennt die Spec nur indirekt; jeder hat einen Test in der genannten Aufgabe.

1. Sprechernamen mit Umlauten, Leerzeichen oder Anführungszeichen müssen in `casting_auto.yaml` unverändert hin und zurück gehen (Task 2).
2. Ein Sprecher ohne Steckbrief wird **nicht geraten**, sondern als offen gemeldet; die Zuteilung bricht dafür nicht ab (Task 6).
3. Nach dem Hören darf ein erneutes `cast --propose` die abgenommene Besetzung nicht verschieben: `--keep` und handgepflegte Einträge bleiben stehen (Task 6).
4. Nach einem Abbruch wegen Limit oder Guthaben dürfen **keine** Fehlerzeilen für nicht gestartete Aufträge in `results.jsonl` stehen, sonst gelten sie später als „fehler“ statt „offen“ und der Wiederaufnahme-Lauf wirkt kaputt (Task 8).
5. Ein ffmpeg ohne `rubberband` meldet bei Varianten sofort eine klare Fehlermeldung, statt jede Datei einzeln scheitern zu lassen (Task 3).
6. Sprecher in verschiedener Schreibung (`Eugen` / `EUGEN`) zählen als derselbe Sprecher bei Auswahl, Etappen und Zuteilung (Task 4).

---

## File Structure

| Datei | Aufgabe |
|---|---|
| `generator/drova_voice/fish_voices.py` (ändern) | `Catalog` mit Stimmen und Varianten, `Candidate`, `load_catalog` |
| `generator/drova_voice/casting.py` (ändern) | Auto-Datei zusätzlich laden, schreiben; Konflikt- und Lastprüfung |
| `generator/drova_voice/encode.py` (ändern) | Variantenrezept im Filter, `require_rubberband` |
| `generator/drova_voice/selection.py` (neu) | Sprecherstatistik, Beispielzeilen, Etappen |
| `generator/drova_voice/profiles.py` (neu) | Steckbriefe: lesen, schreiben, importieren, Pakete für Subagents |
| `generator/drova_voice/assign.py` (neu) | deterministische Stimmenzuteilung |
| `generator/drova_voice/casting_sheet.py` (neu) | Hörseite für die Besetzung |
| `generator/drova_voice/synth.py` (ändern) | Abbruchregel, `SynthStatus` |
| `generator/drova_voice/report.py` (ändern) | Bericht je Sprecher |
| `generator/drova_voice/emote.py` (ändern) | Pakete für Subagents, Import von LLM-Emotionen |
| `generator/drova_voice/pipeline.py` (ändern) | Handler und Argumente: `profile`, `batches`, `cast --propose/--listen`, `--sample`, `--batch`, `emote --prepare/--import`, `report --by-speaker` |
| `casting/fish_voices.yaml` (ändern) | `age`/`type` bei Varianten, `kind_von_oben` als Kind |
| `casting/profiles.jsonl`, `casting/casting_auto.yaml` (neu, erzeugt) | Ergebnis der Operationen |
| `docs/generator.md`, `docs/HANDOFF.md` (ändern) | Bedienung und Stand |

---

### Task 0: Branch und Ausgangslage

**Files:** keine.

- [ ] **Step 1: Branch anlegen und Tests laufen lassen**

```bash
cd /d/Games/Projekte/DrovaTTAI
git switch -c plan-5-casting
cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3
```
Expected: `390 passed` (oder mehr, keine Fehler).

---

### Task 1: Stimmenkatalog mit Varianten, Alter und Typ

**Files:**
- Modify: `generator/drova_voice/fish_voices.py`
- Modify: `casting/fish_voices.yaml`
- Test: `generator/tests/test_fish_voices.py`

**Interfaces:**
- Produces: `AGES = ("kind","jung","mittel","alt")`, `TYPES = ("riese","zwerg","schurke")`; `FishVoice(key,id,label,gender,region,age=None,type=None)`; `FishVariant(key,base,label,gender,age,type,pitch,formant,tempo)`; `Candidate(key,gender,age,type,variant)`; `Catalog(voices, variants)` mit `.synth_table() -> dict[str, FishVoice]` (Variantenschlüssel -> Basisstimme), `.known() -> dict[str, object]` (Stimmen + Varianten), `.candidates() -> list[Candidate]` (nach Schlüssel sortiert); `load_catalog(path) -> Catalog`; `load_fish_voices(path)` bleibt und liefert nur die Stimmen.

- [ ] **Step 1: Failing tests schreiben** (ans Ende von `generator/tests/test_fish_voices.py`, Import oben ergänzen: `from drova_voice.fish_voices import load_catalog`)

```python
VARIANTS_BODY = (
    f"voices:\n"
    f"  lena: {{id: '{ID_A}', label: Lena, gender: f, region: de, age: mittel}}\n"
    f"  leon: {{id: '{ID_B}', label: Leon, gender: m, region: de}}\n"
    "variants:\n"
    "  riese: {base: leon, label: Riese, gender: m, age: mittel, type: riese, pitch: 0.75, formant: 0.85, tempo: 0.93}\n"
)


def _catalog(tmp_path, body):
    p = tmp_path / "fish_voices.yaml"
    p.write_text(body, encoding="utf-8")
    return load_catalog(p)


def test_catalog_reads_voices_variants_and_synth_table(tmp_path):
    c = _catalog(tmp_path, VARIANTS_BODY)
    assert c.voices["lena"].age == "mittel" and c.voices["leon"].age is None
    v = c.variants["riese"]
    assert (v.base, v.gender, v.age, v.type, v.pitch, v.formant, v.tempo) == ("leon", "m", "mittel", "riese", 0.75, 0.85, 0.93)
    assert c.synth_table()["riese"].id == ID_B  # Variante wird mit der Basisstimme erzeugt
    assert set(c.known()) == {"lena", "leon", "riese"}
    assert [(x.key, x.variant) for x in c.candidates()] == [("lena", False), ("leon", False), ("riese", True)]


@pytest.mark.parametrize("variant, message", [
    ("{base: nix, label: X, gender: m, pitch: 1, formant: 1, tempo: 1}", "Basis"),
    ("{base: leon, label: X, gender: q, pitch: 1, formant: 1, tempo: 1}", "gender"),
    ("{base: leon, label: X, gender: m, type: fee, pitch: 1, formant: 1, tempo: 1}", "type"),
    ("{base: leon, label: X, gender: m, age: uralt, pitch: 1, formant: 1, tempo: 1}", "age"),
    ("{base: leon, label: X, gender: m, pitch: 0, formant: 1, tempo: 1}", "pitch"),
    ("{base: leon, label: X, gender: m, pitch: 1, formant: 1}", "tempo"),
])
def test_invalid_variants_are_rejected_in_german(tmp_path, variant, message):
    body = (f"voices:\n  leon: {{id: '{ID_B}', label: Leon, gender: m, region: de}}\nvariants:\n  v: {variant}\n")
    with pytest.raises(ValueError, match=message):
        _catalog(tmp_path, body)


def test_variant_key_must_not_clash_with_a_voice(tmp_path):
    body = (f"voices:\n  leon: {{id: '{ID_B}', label: Leon, gender: m, region: de}}\n"
            "variants:\n  leon: {base: leon, label: X, gender: m, pitch: 1, formant: 1, tempo: 1}\n")
    with pytest.raises(ValueError, match="doppelt"):
        _catalog(tmp_path, body)


def test_invalid_voice_age_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="age"):
        _table(tmp_path, f"voices:\n  x: {{id: '{ID_A}', label: X, gender: f, region: de, age: uralt}}\n")


def test_real_table_variants_carry_age_and_type():
    c = load_catalog(REAL_TABLE)
    assert set(c.variants) == {"alte_frau_rau", "alte_frau", "riese", "zwerg", "schurke_hell", "jugendlicher", "knabe"}
    assert c.variants["knabe"].age == "kind" and c.variants["riese"].type == "riese" and c.variants["zwerg"].type == "zwerg"
    assert c.variants["alte_frau"].gender == "f" and c.variants["alte_frau"].age == "alt"
    assert c.voices["kind_von_oben_578878"].age == "kind"
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_fish_voices.py -q`
Expected: FAIL (`cannot import name 'load_catalog'`).

- [ ] **Step 3: `fish_voices.py` ersetzen**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_ID_RE = re.compile(r"[0-9a-f]{32}")

AGES = ("kind", "jung", "mittel", "alt")
TYPES = ("riese", "zwerg", "schurke")


@dataclass(frozen=True)
class FishVoice:
    key: str
    id: str
    label: str
    gender: str
    region: str
    age: str | None = None
    type: str | None = None


@dataclass(frozen=True)
class FishVariant:
    """Abwandlung einer Basisstimme per ffmpeg (Rezept siehe casting/fish_voices.yaml)."""
    key: str
    base: str
    label: str
    gender: str
    age: str | None
    type: str | None
    pitch: float
    formant: float
    tempo: float


@dataclass(frozen=True)
class Candidate:
    """Eine Stimme oder Variante, wie die Zuteilung sie sieht."""
    key: str
    gender: str
    age: str | None
    type: str | None
    variant: bool


@dataclass(frozen=True)
class Catalog:
    voices: dict[str, FishVoice]
    variants: dict[str, FishVariant]

    def synth_table(self) -> dict[str, FishVoice]:
        """Schlüssel -> Stimme, mit der Fish aufgerufen wird (Varianten nutzen die Basisstimme)."""
        table = dict(self.voices)
        for key, v in self.variants.items():
            table[key] = self.voices[v.base]
        return table

    def known(self) -> dict[str, object]:
        return {**self.voices, **self.variants}

    def candidates(self) -> list[Candidate]:
        out = [Candidate(v.key, v.gender, v.age, v.type, False) for v in self.voices.values()]
        out += [Candidate(v.key, v.gender, v.age, v.type, True) for v in self.variants.values()]
        return sorted(out, key=lambda c: c.key)


def _optional(value, allowed: tuple[str, ...], field: str, key: str, path: Path) -> str | None:
    if value is None or value == "":
        return None
    if value not in allowed:
        raise ValueError(f"{path}: '{key}': {field} muss eines von {', '.join(allowed)} sein")
    return str(value)


def _read(path: Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _voices(raw: dict, path: Path) -> dict[str, FishVoice]:
    voices = raw.get("voices")
    if not isinstance(voices, dict) or not voices:
        raise ValueError(f"{path}: Abschnitt 'voices' fehlt oder ist leer")
    table = {}
    for key, v in voices.items():
        vid = str(v.get("id", ""))
        if not _ID_RE.fullmatch(vid):
            raise ValueError(f"{path}: Stimme '{key}' hat keine gültige ID (32 Hex-Zeichen erwartet)")
        if v.get("gender") not in ("m", "f"):
            raise ValueError(f"{path}: Stimme '{key}': gender muss 'm' oder 'f' sein")
        age = _optional(v.get("age"), AGES, "age", key, path)
        table[str(key).lower()] = FishVoice(str(key).lower(), vid, str(v.get("label", key)), v["gender"],
                                            str(v.get("region", "de")), age, None)
    return table


def _positive(v: dict, name: str, key: str, path: Path) -> float:
    try:
        value = float(v[name])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{path}: Variante '{key}': {name} fehlt oder ist keine Zahl") from None
    if value <= 0:
        raise ValueError(f"{path}: Variante '{key}': {name} muss größer als 0 sein")
    return value


def _variants(raw: dict, voices: dict[str, FishVoice], path: Path) -> dict[str, FishVariant]:
    out: dict[str, FishVariant] = {}
    for key, v in (raw.get("variants") or {}).items():
        name = str(key).lower()
        if name in voices or name in out:
            raise ValueError(f"{path}: Variante '{key}' ist doppelt (auch Stimmenschlüssel sind belegt)")
        base = str(v.get("base", "")).lower()
        if base not in voices:
            raise ValueError(f"{path}: Variante '{key}': Basis '{base}' steht nicht unter voices")
        if v.get("gender") not in ("m", "f"):
            raise ValueError(f"{path}: Variante '{key}': gender muss 'm' oder 'f' sein")
        out[name] = FishVariant(
            name, base, str(v.get("label", key)), v["gender"],
            _optional(v.get("age"), AGES, "age", key, path), _optional(v.get("type"), TYPES, "type", key, path),
            _positive(v, "pitch", key, path), _positive(v, "formant", key, path), _positive(v, "tempo", key, path))
    return out


def load_fish_voices(path: Path) -> dict[str, FishVoice]:
    return _voices(_read(path), Path(path))


def load_catalog(path: Path) -> Catalog:
    raw = _read(path)
    voices = _voices(raw, Path(path))
    return Catalog(voices, _variants(raw, voices, Path(path)))


def resolve_fish_voice(table: dict[str, FishVoice], name_or_id: str) -> FishVoice:
    if name_or_id.lower() in table:
        return table[name_or_id.lower()]
    if _ID_RE.fullmatch(name_or_id):
        return FishVoice(name_or_id[:8], name_or_id, name_or_id, "?", "?")
    raise ValueError(f"Unbekannte Fish-Stimme '{name_or_id}' (Name aus casting/fish_voices.yaml oder 32-stellige ID)")
```

- [ ] **Step 4: `casting/fish_voices.yaml` anpassen**

Im Abschnitt `variants:` die sieben Zeilen ersetzen durch:

```yaml
  alte_frau_rau: {base: "amira_german_b59d11", label: "Alte Frau (rau)", gender: f, age: alt, pitch: 0.9, formant: 1.0, tempo: 0.9}
  alte_frau: {base: "pia_87bebc", label: "Alte Frau", gender: f, age: alt, pitch: 0.88, formant: 0.97, tempo: 0.92}
  riese: {base: "deep_783f5c", label: "Riese", gender: m, age: mittel, type: riese, pitch: 0.75, formant: 0.85, tempo: 0.93}
  zwerg: {base: "erz_hler_c23420", label: "Zwerg", gender: m, age: mittel, type: zwerg, pitch: 0.95, formant: 1.12, tempo: 1.0}
  schurke_hell: {base: "german_d83fad", label: "Schurke (hell)", gender: m, age: mittel, type: schurke, pitch: 1.2, formant: 1.0, tempo: 1.0}
  jugendlicher: {base: "ben_9e3f0e", label: "Jugendlicher", gender: m, age: jung, pitch: 1.2, formant: 1.1, tempo: 1.0}
  knabe: {base: "schales_7ef3ea", label: "Knabe", gender: m, age: kind, pitch: 1.3, formant: 1.18, tempo: 1.03}
```

Beim Rezept-Kommentar die Zeile „Umsetzung als Generator-Schritt kommt in Plan 3.“ ersetzen durch „Umsetzung: `encode` stellt das Rezept dem ffmpeg-Filter voran (Plan 5).“ Bei `kind_von_oben_578878` (Zeile mit `label: "Kind von oben"`) `age: jung` durch `age: kind` ersetzen (Edit-Werkzeug, Zeile ist eindeutig).

- [ ] **Step 5: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_fish_voices.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/fish_voices.py generator/tests/test_fish_voices.py casting/fish_voices.yaml
git commit -m "Add the voice catalog with variants, age and type" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Casting mit Auto-Datei

**Files:**
- Modify: `generator/drova_voice/casting.py`
- Modify: `generator/drova_voice/pipeline.py` (`_load_casting`, `_synth`)
- Test: `generator/tests/test_casting.py`

**Interfaces:**
- Consumes: `Catalog`, `load_catalog` (Task 1).
- Produces: `Casting(default_player, speakers, auto=frozenset())`; `load_casting(path, voices, auto_path=None) -> Casting` (Auto-Einträge zuerst, handgepflegte gewinnen; `Casting.auto` = Namen, die nur aus der Auto-Datei kommen); `write_auto_casting(path, assignments: Mapping[str, str])`; `voice_speakers(lines, casting) -> dict[str, set[str]]`; `tree_conflicts(lines, casting) -> list[tuple[str, str, list[str]]]` (Baum, Stimme, Sprecher); `pipeline.auto_casting_path(cfg)`; `pipeline._load_casting(cfg) -> (Catalog, Casting)`.

- [ ] **Step 1: Failing tests** (ans Ende von `generator/tests/test_casting.py`; Import oben auf `from drova_voice.casting import cast_report, load_casting, tree_conflicts, voice_speakers, write_auto_casting` erweitern)

```python
def test_auto_file_is_overridden_by_manual(tmp_path):
    manual = write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: leon}\n")
    auto = tmp_path / "casting_auto.yaml"
    auto.write_text("speakers:\n  mira: {voice: lena}\n  bo: {voice: leon}\n", encoding="utf-8")
    c = load_casting(manual, VOICES, auto)
    assert c.speakers == {"bo": "leon", "mira": "leon"}
    assert c.auto == frozenset({"bo"})


def test_missing_auto_file_is_fine(tmp_path):
    manual = write(tmp_path, "default_player: leon\nspeakers: {}\n")
    c = load_casting(manual, VOICES, tmp_path / "gibt_es_nicht.yaml")
    assert c.speakers == {} and c.auto == frozenset()


def test_auto_file_with_unknown_voice_names_the_file(tmp_path):
    manual = write(tmp_path, "default_player: leon\nspeakers: {}\n")
    auto = tmp_path / "casting_auto.yaml"
    auto.write_text("speakers:\n  mira: {voice: gibtsnicht}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="casting_auto.yaml.*gibtsnicht"):
        load_casting(manual, VOICES, auto)


def test_auto_file_roundtrip_with_special_names(tmp_path):
    names = {"herr müller": "lena", 'o"brien': "leon", "a b": "lena", "yes": "leon"}
    manual = write(tmp_path, "default_player: leon\nspeakers: {}\n")
    auto = tmp_path / "casting_auto.yaml"
    write_auto_casting(auto, names)
    assert load_casting(manual, VOICES, auto).speakers == names


def tline(key, actor, tree="T1", skip=None, category="dialog"):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw="x", speech="x", stage=(), skip=skip)


def test_voice_speakers_and_tree_conflicts(tmp_path):
    c = load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: lena}\n  bo: {voice: lena}\n  cy: {voice: leon}\n"), VOICES)
    lines = [tline("1", "Mira"), tline("2", "Bo"), tline("3", "Cy"), tline("4", "Mira", tree="T2"), tline("5", "Bo", tree="T3"),
             tline("6", "Mira", tree="T4", skip="gvar"), tline("7", "Fremder")]
    assert voice_speakers(lines, c) == {"lena": {"mira", "bo"}, "leon": {"cy"}}
    assert tree_conflicts(lines, c) == [("T1", "lena", ["bo", "mira"])]
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_casting.py -q`
Expected: FAIL (Import).

- [ ] **Step 3: `casting.py` ersetzen**

```python
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from drova_voice.jsonl import replace_with_retry
from drova_voice.lines import Line

AUTO_HEADER = ("# ERZEUGT von `drova-voice cast --propose`. Nicht von Hand ändern: Korrekturen gehören in\n"
               "# casting/casting.yaml (gewinnt bei Überschneidung).\n")


@dataclass(frozen=True)
class Casting:
    default_player: str
    speakers: dict[str, str]  # Sprechername (klein) -> Stimmen- oder Variantenschlüssel aus fish_voices.yaml
    auto: frozenset[str] = frozenset()  # Sprecher, die nur aus casting_auto.yaml stammen

    def voice_for(self, line: Line) -> str | None:
        if line.category == "player":
            return self.default_player
        return self.speakers.get(line.actor.lower())


@dataclass(frozen=True)
class CastReport:
    missing: dict[str, int]  # Sprecher ohne Stimme -> Zeilenzahl
    usage: dict[str, int]  # Stimme -> Zeilenzahl


def _read_yaml(path: Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Datei muss aus 'Schlüssel: Wert'-Zeilen bestehen")
    return raw


def _speakers_from(path: Path, raw: dict, voices: Mapping[str, object]) -> dict[str, str]:
    speakers: dict[str, str] = {}
    for name, spec in (raw.get("speakers") or {}).items():
        key = str(name).lower()
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: Sprecher '{name}' muss als '{name}: {{voice: <Stimme>}}' angegeben werden")
        voice = str(spec.get("voice", "")).lower()
        if key in speakers:
            raise ValueError(f"{path}: Sprecher '{name}' ist doppelt (Groß-/Kleinschreibung zählt nicht)")
        if voice not in voices:
            raise ValueError(f"{path}: Unbekannte Stimme '{voice}' für Sprecher '{name}' (Schlüssel aus casting/fish_voices.yaml)")
        speakers[key] = voice
    return speakers


def load_casting(path: Path, voices: Mapping[str, object], auto_path: Path | None = None) -> Casting:
    raw = _read_yaml(path)
    default_player = str(raw.get("default_player") or "").lower()
    if default_player not in voices:
        raise ValueError(f"{path}: default_player '{default_player}' fehlt oder steht nicht in fish_voices.yaml")
    manual = _speakers_from(path, raw, voices)
    auto: dict[str, str] = {}
    if auto_path is not None and Path(auto_path).is_file():
        auto = _speakers_from(auto_path, _read_yaml(auto_path), voices)
    return Casting(default_player, {**auto, **manual}, frozenset(n for n in auto if n not in manual))


def write_auto_casting(path: Path, assignments: Mapping[str, str]) -> None:
    import json  # Namen als JSON-String schreiben: gültiges YAML auch mit Umlauten, Leerzeichen und Anführungszeichen

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = AUTO_HEADER + "speakers:\n" + "".join(
        f"  {json.dumps(name, ensure_ascii=False)}: {{voice: {assignments[name]}}}\n" for name in sorted(assignments))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    replace_with_retry(tmp, path)


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


def voice_speakers(lines: Sequence[Line], casting: Casting) -> dict[str, set[str]]:
    """Stimme -> Sprecher (klein), nur Dialogzeilen, die gesprochen werden."""
    out: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        if line.skip or line.category != "dialog":
            continue
        voice = casting.speakers.get(line.actor.lower())
        if voice:
            out[voice].add(line.actor.lower())
    return dict(out)


def tree_conflicts(lines: Sequence[Line], casting: Casting) -> list[tuple[str, str, list[str]]]:
    """(Baum, Stimme, Sprecher), wenn zwei Sprecher in einem Baum dieselbe Stimme haben."""
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for line in lines:
        if line.skip or line.category != "dialog":
            continue
        voice = casting.speakers.get(line.actor.lower())
        if voice:
            seen[(line.tree, voice)].add(line.actor.lower())
    return sorted((tree, voice, sorted(who)) for (tree, voice), who in seen.items() if len(who) > 1)
```

- [ ] **Step 4: `pipeline.py` anpassen**

Importzeilen oben ändern: `from drova_voice.fish_voices import load_fish_voices` wird zu `from drova_voice.fish_voices import load_catalog`. Ersetze `_load_casting`:

```python
def auto_casting_path(cfg: Config) -> Path:
    return cfg.casting_dir / "casting_auto.yaml"


def _load_casting(cfg: Config):
    catalog = load_catalog(cfg.casting_dir / "fish_voices.yaml")
    return catalog, load_casting(cfg.casting_dir / "casting.yaml", catalog.known(), auto_casting_path(cfg))
```

In `_synth` die beiden Stellen anpassen: `voices, casting = _load_casting(cfg)` -> `catalog, casting = _load_casting(cfg)` und `build_jobs(lines, casting, voices, emotions, args.engine)` -> `build_jobs(lines, casting, catalog.synth_table(), emotions, args.engine)`. In `_cast`, `_install`, `_report` heißt die erste Variable `_` und bleibt.

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: alles grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/casting.py generator/drova_voice/pipeline.py generator/tests/test_casting.py
git commit -m "Load the generated casting file under the hand-kept one" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Varianten beim Kodieren

**Files:**
- Modify: `generator/drova_voice/encode.py`
- Modify: `generator/drova_voice/pipeline.py` (`_encode`)
- Create: `generator/tests/ffmpeg_marks.py`
- Test: `generator/tests/test_encode.py`, `generator/tests/test_pipeline_variants.py` (neu)

**Interfaces:**
- Consumes: `FishVariant`, `Catalog.variants`, `Casting.voice_for` (Task 1, 2).
- Produces: `variant_filter(v) -> str`; `require_rubberband(ffmpeg: str) -> None` (wirft `ValueError`); `build_filter(notes, variant=None)`; `ffmpeg_command(ffmpeg, src, dst, notes, variant=None)`; `encode_one(ffmpeg, ffprobe, wav, dst, notes, key, variant=None) -> float`; `run_encode(lines, synth_rows, emotions, audio_dir, workers=4, variants: Mapping[str, FishVariant] | None = None)` (Zeilen-ID -> Variante).

- [ ] **Step 1: Hilfsdatei für Marker**

`generator/tests/ffmpeg_marks.py`:

```python
import shutil
import subprocess

import pytest


def _has_rubberband() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace").stdout
    return " rubberband " in out


needs_rubberband = pytest.mark.skipif(not _has_rubberband() or shutil.which("ffprobe") is None,
                                      reason="ffmpeg mit rubberband und ffprobe nicht installiert")
```

- [ ] **Step 2: Failing tests** (ans Ende von `generator/tests/test_encode.py`; oben ergänzen: `from drova_voice.encode import require_rubberband, variant_filter`, `from drova_voice.fish_voices import FishVariant`, `from ffmpeg_marks import needs_rubberband`)

```python
def variant(pitch=1.0, formant=2.0, tempo=1.0):
    return FishVariant("v", "lena", "V", "f", None, None, pitch, formant, tempo)


def test_variant_filter_follows_the_recipe():
    assert variant_filter(variant()) == ("aresample=44100,asetrate=88200,aresample=44100,"
                                         "rubberband=pitch=0.5:tempo=0.5:formant=preserved")


def test_filter_with_variant_starts_with_the_recipe():
    assert build_filter([], variant()).startswith(variant_filter(variant()) + ",silenceremove")
    assert build_filter([]) == build_filter([], None)


def test_require_rubberband_reports_a_missing_filter(monkeypatch):
    class Result:
        stdout = " ... A->A       atempo             Adjust audio tempo.\n"

    monkeypatch.setattr("drova_voice.encode.subprocess.run", lambda *a, **k: Result())
    with pytest.raises(ValueError, match="rubberband"):
        require_rubberband("ffmpeg")


def test_require_rubberband_accepts_the_filter(monkeypatch):
    class Result:
        stdout = " ..C rubberband        A->A       Apply time-stretching and pitch-shifting.\n"

    monkeypatch.setattr("drova_voice.encode.subprocess.run", lambda *a, **k: Result())
    assert require_rubberband("ffmpeg") is None


def test_run_encode_with_a_variant_checks_rubberband_before_anything_else(tmp_path, monkeypatch):
    def missing(ffmpeg):
        raise ValueError("ffmpeg ohne rubberband")

    monkeypatch.setattr("drova_voice.encode.find_tools", lambda: ("ffmpeg", "ffprobe"))
    monkeypatch.setattr("drova_voice.encode.require_rubberband", missing)
    with pytest.raises(ValueError, match="rubberband"):
        run_encode([line()], {"T|P|Plh_1": {"id": "T|P|Plh_1", "ok": True, "wav": "x.wav", "key": "k"}}, {}, tmp_path, 1,
                   {"T|P|Plh_1": variant()})


@needs_rubberband
def test_encode_one_applies_the_variant_and_restamps(tmp_path):
    ffmpeg, ffprobe = find_tools()
    wav = tmp_path / "in.wav"
    sine_wav(wav, seconds=1.0, lead_silence=0.0, rate=44100)
    dst = tmp_path / "out" / "x.ogg"
    plain = encode_one(ffmpeg, ffprobe, wav, dst, [], "k")
    before = dst.stat().st_mtime_ns
    slow = encode_one(ffmpeg, ffprobe, wav, dst, [], "k", variant(pitch=1.0, formant=1.0, tempo=0.5))
    assert dst.stat().st_mtime_ns != before  # anderes Rezept -> neu kodiert
    assert slow > plain * 1.5  # Tempo 0.5 dehnt die Zeit
```

`generator/tests/test_pipeline_variants.py` (neu):

```python
from drova_voice.cli import main
from ffmpeg_marks import needs_rubberband

FISH = ("voices:\n  lena: {id: '3937b44b604249f18b94913daef94043', label: Lena, gender: f}\n"
        "  leon: {id: '7b7c88bf825a4ab3bca27d55c26ddf16', label: Leon, gender: m}\n"
        "variants:\n  alte: {base: lena, label: Alte, gender: f, age: alt, pitch: 0.9, formant: 1.0, tempo: 0.9}\n")


@needs_rubberband
def test_encode_uses_the_variant_of_the_speaker(pipeline_repo, guarded):
    (pipeline_repo.casting / "fish_voices.yaml").write_text(FISH, encoding="utf-8")
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers:\n  mira: {voice: alte}\n", encoding="utf-8")
    cfg = str(pipeline_repo.cfg)
    assert main(["--config", cfg, "extract"]) == 0
    assert guarded(lambda: main(["--config", cfg, "synth", "--engine", "fake", "--workers", "2"])) == 0
    assert main(["--config", cfg, "encode"]) == 0
    stamps = list((pipeline_repo.repo / "out" / "audio" / "de" / "dialog").glob("*.stamp"))
    assert len(stamps) == 2 and all("rubberband" in s.read_text(encoding="utf-8") for s in stamps)
    player_stamps = list((pipeline_repo.repo / "out" / "audio" / "de" / "player").rglob("*.stamp"))
    assert player_stamps and all("rubberband" not in s.read_text(encoding="utf-8") for s in player_stamps)
```

- [ ] **Step 3: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_encode.py tests/test_pipeline_variants.py -q`
Expected: FAIL (Import `require_rubberband`).

- [ ] **Step 4: `encode.py` ändern**

Oben nach `WHISPER_GAIN_DB = -6` ergänzen und die Funktionen `build_filter`, `ffmpeg_command`, `_stamp`, `encode_one`, `run_encode` ersetzen; `find_tools` bekommt direkt darunter `require_rubberband`:

```python
VARIANT_RATE = 44100  # Rezept in casting/fish_voices.yaml ist auf 44,1 kHz gerechnet


def variant_filter(v) -> str:
    """Rezept aus casting/fish_voices.yaml: formant (Vokaltrakt) über die Abtastrate, pitch/tempo über rubberband."""
    return (f"aresample={VARIANT_RATE},asetrate={round(VARIANT_RATE * v.formant)},aresample={VARIANT_RATE},"
            f"rubberband=pitch={v.pitch / v.formant:g}:tempo={v.tempo / v.formant:g}:formant=preserved")


def build_filter(notes: Sequence[str], variant=None) -> str:
    # Stille vorn und hinten entfernen (hinten: Umkehren, vorn trimmen, zurückdrehen), dann auf -16 LUFS.
    # (aresample vor UND nach loudnorm: mit ffmpeg 7.0 bricht jede andere Stellung des Filters ab.)
    parts = [variant_filter(variant)] if variant is not None else []
    parts += [_TRIM, "areverse", _TRIM, "areverse", f"aresample={SAMPLE_RATE}", LOUDNORM, f"aresample={SAMPLE_RATE}"]
    if "whisper" in notes:  # *flüstert*: leiser (das "gehauchte" kommt später, falls der Hörtest es verlangt)
        parts.append(f"volume={WHISPER_GAIN_DB}dB")
    return ",".join(parts)


def ffmpeg_command(ffmpeg: str, src: Path, dst: Path, notes: Sequence[str], variant=None) -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", build_filter(notes, variant),
            "-ac", "1", "-c:a", "libvorbis", "-q:a", "4", str(dst)]
```

`require_rubberband` (nach `find_tools`):

```python
def require_rubberband(ffmpeg: str) -> None:
    out = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace")
    if " rubberband " not in out.stdout:
        raise ValueError("Dieses ffmpeg hat den Filter 'rubberband' nicht; er wird für Stimmenvarianten gebraucht")
```

`_stamp`, `encode_one`, `run_encode`:

```python
def _stamp(key: str, notes: Sequence[str], variant=None) -> str:
    return f"{key}|{build_filter(notes, variant)}"


def encode_one(ffmpeg: str, ffprobe: str, wav: Path, dst: Path, notes: Sequence[str], key: str, variant=None) -> float:
    dst = Path(dst)
    stamp_file = dst.with_suffix(".stamp")
    stamp = _stamp(key, notes, variant)
    if dst.is_file() and stamp_file.is_file() and stamp_file.read_text(encoding="utf-8") == stamp:
        return probe_duration(ffprobe, dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(f"{dst.stem}.part.ogg")
    proc = subprocess.run(ffmpeg_command(ffmpeg, Path(wav), part, notes, variant), capture_output=True, text=True, errors="replace")
    if proc.returncode != 0 or not part.is_file():
        part.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg Exit-Code {proc.returncode}: {proc.stderr.strip()[:200]}")
    replace_with_retry(part, dst)
    stamp_file.write_text(stamp, encoding="utf-8")
    return probe_duration(ffprobe, dst)


def run_encode(lines: Sequence[Line], synth_rows: Mapping[str, dict], emotions: Mapping[str, EmotionTag],
               audio_dir: Path, workers: int = 4, variants: Mapping[str, object] | None = None) -> tuple[list[dict], list[str]]:
    ffmpeg, ffprobe = find_tools()
    if variants:
        require_rubberband(ffmpeg)
    todo = [(l, synth_rows[l.id]) for l in lines if not l.skip and l.id in synth_rows and synth_rows[l.id].get("ok")]

    def work(item):
        line, row = item
        wav = Path(row["wav"] or "")
        if not wav.is_file():
            return None, f"{line.id}: WAV fehlt ({wav})"
        notes = emotions[line.id].notes if line.id in emotions else []
        rel = rel_audio_path(line)
        try:
            duration = encode_one(ffmpeg, ffprobe, wav, Path(audio_dir) / rel, notes, row["key"], (variants or {}).get(line.id))
        except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as e:
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

- [ ] **Step 5: `pipeline._encode` ersetzen**

```python
def _encode(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    synth_rows = latest_by_id(read_jsonl_lenient(synth_results_path(cfg)))
    if not synth_rows:
        return _fail(f"{synth_results_path(cfg)} fehlt oder ist leer (zuerst `drova-voice synth` ausführen)")
    try:
        catalog, casting = _load_casting(cfg)
        emotions = read_emotions(emotions_path(cfg))
        variants = {l.id: catalog.variants[casting.voice_for(l)] for l in lines
                    if not l.skip and casting.voice_for(l) in catalog.variants}
        rows, errors = run_encode(lines, synth_rows, emotions, audio_dir(cfg), args.workers, variants)
    except (OSError, ValueError) as e:
        return _fail(str(e))
    merged = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    merged.update({r["id"]: r for r in rows})
    write_jsonl(encoded_path(cfg), merged.values())
    print(f"{len(rows)} kodiert -> {audio_dir(cfg)}; {len(errors)} Fehler")
    for e in errors[:10]:
        print(f"FEHLER {e}", file=sys.stderr)
    return 1 if errors else 0
```

- [ ] **Step 6: Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün (Rubberband-Tests laufen, wenn ffmpeg den Filter hat).

- [ ] **Step 7: Commit**

```bash
git add generator/drova_voice/encode.py generator/drova_voice/pipeline.py generator/tests/ffmpeg_marks.py generator/tests/test_encode.py generator/tests/test_pipeline_variants.py
git commit -m "Apply voice variants while encoding" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Auswahl nach Sprecher, Beispielzeilen und Etappen

**Files:**
- Create: `generator/drova_voice/selection.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_selection.py` (neu), `generator/tests/test_pipeline_selection.py` (neu)

**Interfaces:**
- Consumes: `Line` (`drova_voice.lines`).
- Produces: `SpeakerStat(name, display, lines, chars, trees: frozenset[str])`; `is_named_dialog(line) -> bool`; `speaker_stats(lines) -> list[SpeakerStat]` (nach Zeilen absteigend, dann Name); `sample_lines(lines) -> list[Line]`; `Batch(n, speakers: tuple[str,...], lines, chars, player)`; `DEFAULT_BATCH_CHARS = 100_000`; `plan_batches(lines, max_chars=DEFAULT_BATCH_CHARS) -> list[Batch]`; `write_batches(path, batches, max_chars)`; `read_batches(path) -> list[Batch]`; `batch_lines(lines, batch) -> list[Line]`; in `pipeline`: `batches_path(cfg)`, `_add_selection(parser)`, `_selected` versteht `--sample` und `--batch N`, neues Kommando `batches [--max-chars N]`.

- [ ] **Step 1: Failing tests**

`generator/tests/test_selection.py`:

```python
from drova_voice.lines import Line
from drova_voice.selection import (Batch, batch_lines, plan_batches, read_batches, sample_lines, speaker_stats,
                                   write_batches)


def line(key, actor="Anna", speech="x" * 40, tree="T1", category="dialog", generic=False, skip=None):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=generic, raw=speech, speech="" if skip else speech, stage=(), skip=skip)


def test_speaker_stats_count_named_dialog_only_and_ignore_case():
    lines = [line("1", "Anna"), line("2", "ANNA", tree="T2"), line("3", "Bob"), line("4", "NPC", generic=True),
             line("5", "Cy", category="bark"), line("6", "Player", category="player"), line("7", "Dee", skip="gvar")]
    stats = speaker_stats(lines)
    assert [(s.name, s.display, s.lines, s.chars) for s in stats] == [("anna", "Anna", 2, 80), ("bob", "Bob", 1, 40)]
    assert stats[0].trees == frozenset({"T1", "T2"})


def test_sample_lines_pick_one_per_speaker_closest_to_80_characters():
    lines = [line("1", "Anna", "k" * 10), line("2", "Anna", "m" * 75), line("3", "Anna", "l" * 200),
             line("4", "Bob", "b" * 30), line("5", "NPC", generic=True)]
    assert [l.id for l in sample_lines(lines)] == ["T1|P|2", "T1|P|4"]


def test_plan_batches_pack_by_characters_and_put_the_player_in_the_last_one():
    lines = ([line(f"a{i}", "Anna") for i in range(3)] + [line(f"b{i}", "Bob") for i in range(2)] + [line("c", "Cy")]
             + [line("p", "Player", category="player")])
    batches = plan_batches(lines, max_chars=150)
    assert [(b.n, b.speakers, b.lines, b.chars, b.player) for b in batches] == [
        (1, ("anna",), 3, 120, False), (2, ("bob", "cy"), 3 + 1, 120 + 40, True)]


def test_plan_batches_without_lines_is_empty():
    assert plan_batches([]) == []


def test_batch_lines_select_the_speakers_lines_and_the_player_only_when_marked():
    lines = [line("1", "Anna"), line("2", "Bob"), line("3", "NPC", generic=True), line("4", "Player", category="player")]
    assert [l.id for l in batch_lines(lines, Batch(1, ("anna",), 1, 40, False))] == ["T1|P|1"]
    assert [l.id for l in batch_lines(lines, Batch(2, ("bob",), 1, 40, True))] == ["T1|P|2", "T1|P|4"]


def test_batches_roundtrip(tmp_path):
    batches = [Batch(1, ("anna", "bob"), 5, 200, False), Batch(2, ("cy",), 1, 40, True)]
    write_batches(tmp_path / "data" / "batches.json", batches, 150)
    assert read_batches(tmp_path / "data" / "batches.json") == batches
```

`generator/tests/test_pipeline_selection.py`:

```python
from drova_voice.cli import main
from drova_voice.jsonl import read_jsonl_lenient

TREE = "DT_Test_NPC_Mira|Dialog/NPC_Mira|"


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def test_batches_command_lists_the_speakers_and_writes_the_plan(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "batches") == 0
    out = capsys.readouterr().out
    assert "Etappe 1" in out and "Mira" in out and (pipeline_repo.data / "batches.json").is_file()


def test_synth_batch_runs_the_speaker_and_the_player(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    run(pipeline_repo, "batches")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--batch", "1")) == 0
    ids = sorted(r["id"] for r in read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl"))
    assert ids == [TREE + "Plh_1", TREE + "Plh_2", TREE + "Plh_3"]


def test_unknown_batch_and_missing_plan_are_clear_errors(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "synth", "--engine", "fake", "--batch", "1") == 2
    assert "batches" in capsys.readouterr().err
    run(pipeline_repo, "batches")
    assert run(pipeline_repo, "synth", "--engine", "fake", "--batch", "7") == 2
    assert "Etappe 7" in capsys.readouterr().err


def test_synth_sample_runs_one_line_per_speaker(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--sample")) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl")
    assert [r["id"] for r in rows] == [TREE + "Plh_1"]
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_selection.py tests/test_pipeline_selection.py -q`
Expected: FAIL (Modul fehlt).

- [ ] **Step 3: `generator/drova_voice/selection.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from drova_voice.lines import Line

DEFAULT_BATCH_CHARS = 100_000
SAMPLE_TARGET_CHARS = 80  # Beispielzeile: mittellang, damit Stimme und Betonung hörbar sind


@dataclass(frozen=True)
class SpeakerStat:
    name: str  # klein
    display: str  # Schreibung der ersten Zeile
    lines: int
    chars: int
    trees: frozenset[str]


@dataclass(frozen=True)
class Batch:
    n: int
    speakers: tuple[str, ...]
    lines: int
    chars: int
    player: bool  # enthält zusätzlich die Aussagen des Spielers


def is_named_dialog(line: Line) -> bool:
    """Zeile eines benannten Sprechers, die gesprochen wird (Plan 5: ohne Barks, generische Sprecher und Spieler)."""
    return not line.skip and line.category == "dialog" and not line.generic and bool(line.actor)


def speaker_stats(lines: Sequence[Line]) -> list[SpeakerStat]:
    acc: dict[str, list] = {}
    for line in lines:
        if not is_named_dialog(line):
            continue
        entry = acc.setdefault(line.actor.lower(), [line.actor, 0, 0, set()])
        entry[1] += 1
        entry[2] += len(line.speech)
        entry[3].add(line.tree)
    stats = [SpeakerStat(name, v[0], v[1], v[2], frozenset(v[3])) for name, v in acc.items()]
    return sorted(stats, key=lambda s: (-s.lines, s.name))


def _sample_rank(line: Line) -> tuple[int, str]:
    return abs(len(line.speech) - SAMPLE_TARGET_CHARS), line.id


def sample_lines(lines: Sequence[Line]) -> list[Line]:
    """Je benanntem Sprecher eine Zeile (deterministisch), nach Sprechername sortiert."""
    best: dict[str, Line] = {}
    for line in lines:
        if not is_named_dialog(line):
            continue
        name = line.actor.lower()
        if name not in best or _sample_rank(line) < _sample_rank(best[name]):
            best[name] = line
    return [best[name] for name in sorted(best)]


def plan_batches(lines: Sequence[Line], max_chars: int = DEFAULT_BATCH_CHARS) -> list[Batch]:
    groups: list[tuple[list[str], int, int]] = []
    names: list[str] = []
    n_lines = n_chars = 0
    for s in speaker_stats(lines):
        if names and n_chars + s.chars > max_chars:
            groups.append((names, n_lines, n_chars))
            names, n_lines, n_chars = [], 0, 0
        names.append(s.name)
        n_lines += s.lines
        n_chars += s.chars
    if names:
        groups.append((names, n_lines, n_chars))
    batches = [Batch(i, tuple(g[0]), g[1], g[2], False) for i, g in enumerate(groups, start=1)]
    player = [l for l in lines if l.category == "player" and not l.skip]
    if player:
        extra_chars = sum(len(l.speech) for l in player)
        if batches:
            last = batches[-1]
            batches[-1] = replace(last, lines=last.lines + len(player), chars=last.chars + extra_chars, player=True)
        else:
            batches.append(Batch(1, (), len(player), extra_chars, True))
    return batches


def write_batches(path: Path, batches: Sequence[Batch], max_chars: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"max_chars": max_chars, "batches": [
        {"n": b.n, "speakers": list(b.speakers), "lines": b.lines, "chars": b.chars, "player": b.player} for b in batches]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def read_batches(path: Path) -> list[Batch]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return [Batch(int(b["n"]), tuple(b["speakers"]), int(b["lines"]), int(b["chars"]), bool(b["player"]))
            for b in data["batches"]]


def batch_lines(lines: Sequence[Line], batch: Batch) -> list[Line]:
    names = set(batch.speakers)
    return [l for l in lines
            if (l.category == "dialog" and not l.generic and l.actor.lower() in names)
            or (batch.player and l.category == "player")]
```

- [ ] **Step 4: `pipeline.py` anpassen**

Imports ergänzen: `from drova_voice.selection import DEFAULT_BATCH_CHARS, batch_lines, plan_batches, read_batches, sample_lines, speaker_stats, write_batches`.

`_selected` ersetzen:

```python
def batches_path(cfg: Config) -> Path:
    return cfg.data_dir / "batches.json"


def _selected(cfg: Config, args: argparse.Namespace) -> list[Line] | None:
    """Zeilen aus data/lines.jsonl, gefiltert nach --npc (ganze Bäume), --sample (eine Zeile je Sprecher) und
    --batch N (Etappe); None (mit Meldung), wenn die Auswahl nicht möglich ist."""
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
    if getattr(args, "sample", False):
        lines = sample_lines(lines)
    batch_n = getattr(args, "batch", None)
    if batch_n is not None:
        if not batches_path(cfg).is_file():
            _fail(f"{batches_path(cfg)} fehlt (zuerst `drova-voice batches` ausführen)")
            return None
        chosen = [b for b in read_batches(batches_path(cfg)) if b.n == batch_n]
        if not chosen:
            _fail(f"Etappe {batch_n} gibt es nicht (siehe `drova-voice batches`)")
            return None
        lines = batch_lines(lines, chosen[0])
    return lines
```

Neuer Handler (vor `HANDLERS`):

```python
def _batches(cfg: Config, args: argparse.Namespace) -> int:
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    batches = plan_batches(lines, args.max_chars)
    write_batches(batches_path(cfg), batches, args.max_chars)
    display = {s.name: s.display for s in speaker_stats(lines)}
    for b in batches:
        who = ", ".join(display[n] for n in b.speakers[:6]) + (", ..." if len(b.speakers) > 6 else "")
        print(f"Etappe {b.n}: {len(b.speakers)} Sprecher{' + Spieler' if b.player else ''}, {b.lines} Zeilen, {b.chars} Zeichen ({who})")
    print(f"{len(batches)} Etappen, {sum(b.chars for b in batches)} Zeichen -> {batches_path(cfg)}")
    return 0
```

`HANDLERS` um `"batches": _batches,` ergänzen. Vor `add_parsers` die Hilfsfunktion:

```python
def _add_selection(parser, npc_help: str = "nur Bäume, in denen dieser NPC spricht") -> None:
    parser.add_argument("--npc", help=npc_help)
    parser.add_argument("--sample", action="store_true", help="nur eine Beispielzeile je Sprecher (Hörstufe)")
    parser.add_argument("--batch", type=int, help="nur die Zeilen dieser Etappe (siehe `batches`)")
```

In `add_parsers` die Zeilen `sy.add_argument("--npc", ...)`, `en.add_argument("--npc", ...)`, `ins.add_argument("--npc", ...)`, `rp.add_argument("--npc", ...)`, `pv.add_argument("--npc", ...)` jeweils ersetzen durch `_add_selection(sy)`, `_add_selection(en)`, `_add_selection(ins, "nur Bäume, in denen dieser NPC spricht (frühere Einträge bleiben erhalten)")`, `_add_selection(rp)`, `_add_selection(pv)`. Nach `_add_selection(pv)` anfügen:

```python
    bt = sub.add_parser("batches", help="Etappen für den Vollauf planen (data/batches.json)")
    bt.add_argument("--max-chars", type=int, default=DEFAULT_BATCH_CHARS, help="Zeichen je Etappe (Standard 100000)")
```

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/selection.py generator/drova_voice/pipeline.py generator/tests/test_selection.py generator/tests/test_pipeline_selection.py
git commit -m "Add sample and batch selection by speaker" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Steckbriefe

**Files:**
- Create: `generator/drova_voice/profiles.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_profiles.py` (neu), `generator/tests/test_pipeline_profile.py` (neu)

**Interfaces:**
- Consumes: `AGES`, `TYPES` (Task 1), `SpeakerStat`, `speaker_stats`, `is_named_dialog` (Task 4).
- Produces: `Profile(speaker, gender, age, type, confidence, note, source)` mit `to_dict()` / `Profile.from_dict(d)`; `LOW_CONFIDENCE = 0.6`; `read_profiles(path) -> dict[str, Profile]`; `write_profiles(path, profiles: Iterable[Profile])`; `merge_import(existing, rows, known) -> tuple[dict[str, Profile], list[str]]`; `prepare_packets(lines, profiles, size=20, max_own=40, max_mentions=12, include_known=False) -> list[list[dict]]`; `pipeline.profiles_path(cfg)`; Kommando `profile` mit `--prepare [--size N] [--all]`, `--import DATEI...`, `--set NAME --gender m|f --age ... [--type ...] [--note ...]`, ohne Option `--show`.

- [ ] **Step 1: Failing tests**

`generator/tests/test_profiles.py`:

```python
import pytest

from drova_voice.lines import Line
from drova_voice.profiles import Profile, merge_import, prepare_packets, read_profiles, write_profiles


def line(key, actor="Anna", speech="Hallo.", tree="T1", category="dialog", generic=False, skip=None):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=generic, raw=speech, speech=speech, stage=(), skip=skip)


def prof(speaker="anna", source="llm", **kw):
    d = {"speaker": speaker, "gender": "f", "age": "mittel", "type": "", "confidence": 0.9, "note": "ruhig", "source": source}
    return Profile.from_dict({**d, **kw})


@pytest.mark.parametrize("bad, message", [
    ({"gender": "x"}, "gender"), ({"age": "uralt"}, "age"), ({"type": "fee"}, "type"),
    ({"confidence": 2}, "confidence"), ({"confidence": "viel"}, "confidence"), ({"speaker": " "}, "speaker"),
    ({"source": "orakel"}, "source"),
])
def test_invalid_profiles_are_rejected_in_german(bad, message):
    with pytest.raises(ValueError, match=message):
        prof(**bad)


def test_profile_normalizes_speaker_type_and_truncates_the_note():
    p = prof(speaker=" Anna ", type=None, note="x" * 500)
    assert p.speaker == "anna" and p.type is None and len(p.note) == 200


def test_roundtrip_and_sorting(tmp_path):
    path = tmp_path / "profiles.jsonl"
    write_profiles(path, [prof("zoe"), prof("anna", type="riese")])
    loaded = read_profiles(path)
    assert list(loaded) == ["anna", "zoe"] and loaded["anna"].type == "riese"
    assert read_profiles(tmp_path / "nix.jsonl") == {}


def test_read_profiles_names_the_bad_line(tmp_path):
    path = tmp_path / "profiles.jsonl"
    path.write_text('{"speaker": "a", "gender": "q", "age": "jung"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Zeile 1"):
        read_profiles(path)


def test_merge_import_rules():
    existing = {"anna": prof("anna", source="manual", gender="m"), "bob": prof("bob", source="llm", gender="m")}
    rows = [{"speaker": "Anna", "gender": "f", "age": "jung"},          # manual bleibt
            {"speaker": "bob", "gender": "f", "age": "alt", "source": "manual", "confidence": 0.7},  # llm wird ersetzt, Quelle erzwungen
            {"speaker": "cy", "gender": "m", "age": "kind"},
            {"speaker": "unbekannt", "gender": "m", "age": "kind"},
            {"speaker": "dee", "gender": "q", "age": "kind"}]
    merged, errors = merge_import(existing, rows, known={"anna", "bob", "cy", "dee"})
    assert merged["anna"].gender == "m" and merged["anna"].source == "manual"
    assert merged["bob"].gender == "f" and merged["bob"].source == "llm"
    assert merged["cy"].age == "kind" and "dee" not in merged and "unbekannt" not in merged
    assert len(errors) == 2 and any("unbekannt" in e for e in errors) and any("dee" in e for e in errors)


def test_prepare_packets_only_missing_named_speakers_with_mentions():
    lines = ([line(f"a{i}", "Anna", f"Anna sagt Nummer {i}.") for i in range(5)]
             + [line("b1", "Bob", "Frag doch Anna, sie weiß es."), line("b2", "Bob", "Anna-Maria ist nicht gemeint? Doch.")]
             + [line("n", "NPC", "Anna!", generic=True), line("p", "Player", "Anna?", category="player"),
                line("g", "Cy", "Anna", skip="gvar")])
    packets = prepare_packets(lines, {}, size=1, max_own=3, max_mentions=5)
    assert [[e["speaker"] for e in p] for p in packets] == [["anna"], ["bob"]]
    anna = packets[0][0]
    assert anna["display"] == "Anna" and anna["lines"] == 5 and len(anna["own"]) == 3
    assert {m["by"] for m in anna["mentions"]} == {"Bob"} and len(anna["mentions"]) == 2
    assert [e["speaker"] for p in prepare_packets(lines, {"anna": prof("anna")}, size=5) for e in p] == ["bob"]
    assert [e["speaker"] for p in prepare_packets(lines, {"anna": prof("anna")}, size=5, include_known=True) for e in p] == ["anna", "bob"]
```

`generator/tests/test_pipeline_profile.py`:

```python
import json

from drova_voice.cli import main
from drova_voice.profiles import read_profiles


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def test_set_show_and_import(pipeline_repo, tmp_path, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--set", "Mira", "--gender", "f", "--age", "mittel", "--note", "ruhig") == 0
    profiles = read_profiles(pipeline_repo.casting / "profiles.jsonl")
    assert profiles["mira"].source == "manual" and profiles["mira"].note == "ruhig"
    capsys.readouterr()
    assert run(pipeline_repo, "profile") == 0
    out = capsys.readouterr().out
    assert "Mira" in out and "mittel" in out and "manual" in out
    incoming = tmp_path / "result.jsonl"
    incoming.write_text(json.dumps({"speaker": "fremder", "gender": "m", "age": "alt"}) + "\n", encoding="utf-8")
    assert run(pipeline_repo, "profile", "--import", str(incoming)) == 1
    assert "fremder" in capsys.readouterr().err


def test_set_needs_gender_and_age(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--set", "mira") == 2
    assert "--gender" in capsys.readouterr().err


def test_prepare_writes_packets_for_speakers_without_profile(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--prepare", "--size", "5") == 0
    packet = json.loads((pipeline_repo.repo / "out" / "subagent" / "profile" / "packet_001.json").read_text(encoding="utf-8"))
    assert [e["speaker"] for e in packet] == ["mira"]
    assert "1 Sprecher in 1 Paketen" in capsys.readouterr().out
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_profiles.py tests/test_pipeline_profile.py -q`
Expected: FAIL (Modul fehlt).

- [ ] **Step 3: `generator/drova_voice/profiles.py`**

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from drova_voice.fish_voices import AGES, TYPES
from drova_voice.jsonl import write_jsonl
from drova_voice.lines import Line
from drova_voice.selection import is_named_dialog, speaker_stats

SOURCES = ("llm", "manual")
LOW_CONFIDENCE = 0.6
MAX_NOTE = 200


@dataclass(frozen=True)
class Profile:
    speaker: str  # klein
    gender: str  # m | f
    age: str  # kind | jung | mittel | alt
    type: str | None  # riese | zwerg | schurke | None
    confidence: float
    note: str  # ein Satz zum Charakter, keine Zitate (liegt im Git)
    source: str  # llm | manual

    def to_dict(self) -> dict:
        return {"speaker": self.speaker, "gender": self.gender, "age": self.age, "type": self.type or "",
                "confidence": self.confidence, "note": self.note, "source": self.source}

    @classmethod
    def from_dict(cls, d: Mapping) -> "Profile":
        speaker = str(d.get("speaker") or "").strip().lower()
        if not speaker:
            raise ValueError("speaker fehlt")
        if d.get("gender") not in ("m", "f"):
            raise ValueError(f"{speaker}: gender muss 'm' oder 'f' sein")
        if d.get("age") not in AGES:
            raise ValueError(f"{speaker}: age muss eines von {', '.join(AGES)} sein")
        type_ = d.get("type") or None
        if type_ is not None and type_ not in TYPES:
            raise ValueError(f"{speaker}: type muss leer oder eines von {', '.join(TYPES)} sein")
        try:
            confidence = float(d.get("confidence", 0.5))
        except (TypeError, ValueError):
            raise ValueError(f"{speaker}: confidence ist keine Zahl") from None
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"{speaker}: confidence außerhalb 0..1")
        source = d.get("source", "llm")
        if source not in SOURCES:
            raise ValueError(f"{speaker}: source muss llm oder manual sein")
        return cls(speaker, d["gender"], d["age"], type_, confidence, str(d.get("note") or "").strip()[:MAX_NOTE], source)


def read_profiles(path: Path) -> dict[str, Profile]:
    path = Path(path)
    if not path.exists():
        return {}
    result: dict[str, Profile] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), start=1):
        if not raw.strip():
            continue
        try:
            p = Profile.from_dict(json.loads(raw))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"{path}: Zeile {number} ungültig ({e})") from e
        result[p.speaker] = p
    return result


def write_profiles(path: Path, profiles: Iterable[Profile]) -> None:
    write_jsonl(path, (p.to_dict() for p in sorted(profiles, key=lambda p: p.speaker)))


def merge_import(existing: Mapping[str, Profile], rows: Iterable[Mapping], known: set[str]) -> tuple[dict[str, Profile], list[str]]:
    """LLM-Steckbriefe einlesen: Quelle wird auf llm gesetzt, manual-Zeilen bleiben, unbekannte Sprecher werden gemeldet."""
    merged = dict(existing)
    errors: list[str] = []
    for number, row in enumerate(rows, start=1):
        try:
            p = Profile.from_dict({**row, "source": "llm"})
        except ValueError as e:
            errors.append(f"Zeile {number}: {e}")
            continue
        if p.speaker not in known:
            errors.append(f"Zeile {number}: Sprecher '{p.speaker}' kommt im Export nicht vor")
            continue
        if p.speaker in merged and merged[p.speaker].source == "manual":
            continue
        merged[p.speaker] = p
    return merged, errors


def prepare_packets(lines: Sequence[Line], profiles: Mapping[str, Profile], size: int = 20, max_own: int = 40,
                    max_mentions: int = 12, include_known: bool = False) -> list[list[dict]]:
    """Pakete für Subagents: je Sprecher ein Auszug seiner Zeilen und Zeilen anderer, die ihn nennen."""
    dialog = [l for l in lines if is_named_dialog(l)]
    own_by_name: dict[str, list[Line]] = {}
    for l in sorted(dialog, key=lambda l: l.id):
        own_by_name.setdefault(l.actor.lower(), []).append(l)
    entries = []
    for s in speaker_stats(lines):
        if s.name in profiles and not include_known:
            continue
        own = own_by_name[s.name]
        own = own[:: max(1, len(own) // max_own)][:max_own]
        pattern = re.compile(rf"\b{re.escape(s.display)}\b")
        mentions = [{"by": l.actor, "text": l.speech} for l in dialog
                    if l.actor.lower() != s.name and pattern.search(l.speech)][:max_mentions]
        entries.append({"speaker": s.name, "display": s.display, "lines": s.lines, "trees": sorted(s.trees)[:8],
                        "own": [l.speech for l in own], "mentions": mentions})
    return [entries[i:i + size] for i in range(0, len(entries), size)]
```

- [ ] **Step 4: `pipeline.py` anpassen**

Imports: `from drova_voice.profiles import Profile, merge_import, prepare_packets, read_profiles, write_profiles`.

Handler (vor `HANDLERS`):

```python
def profiles_path(cfg: Config) -> Path:
    return cfg.casting_dir / "profiles.jsonl"


def _profile(cfg: Config, args: argparse.Namespace) -> int:
    try:
        profiles = read_profiles(profiles_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    if args.set:
        if not args.gender or not args.age:
            return _fail("--set braucht --gender und --age")
        try:
            p = Profile.from_dict({"speaker": args.set, "gender": args.gender, "age": args.age, "type": args.type,
                                   "confidence": 1.0, "note": args.note or "", "source": "manual"})
        except ValueError as e:
            return _fail(str(e))
        profiles[p.speaker] = p
        write_profiles(profiles_path(cfg), profiles.values())
        print(f"{p.speaker}: {p.gender}, {p.age}{', ' + p.type if p.type else ''} -> {profiles_path(cfg)}")
        return 0
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    if args.prepare:
        packets = prepare_packets(lines, profiles, args.size, include_known=args.all)
        out = cfg.out_dir / "subagent" / "profile"
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("packet_*.json"):
            old.unlink()
        for i, packet in enumerate(packets, start=1):
            (out / f"packet_{i:03d}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{sum(len(p) for p in packets)} Sprecher in {len(packets)} Paketen -> {out}")
        return 0
    if args.import_files:
        rows = [row for f in args.import_files for row in read_jsonl_lenient(f)]
        merged, errors = merge_import(profiles, rows, {s.name for s in speaker_stats(lines)})
        write_profiles(profiles_path(cfg), merged.values())
        print(f"{len(merged)} Steckbriefe ({len(merged) - len(profiles)} neu) -> {profiles_path(cfg)}")
        for e in errors[:20]:
            print(f"FEHLER {e}", file=sys.stderr)
        return 1 if errors else 0
    stats = speaker_stats(lines)
    for s in stats:
        p = profiles.get(s.name)
        if p is None:
            print(f"{s.display} ({s.lines}): kein Steckbrief")
        else:
            flag = " UNSICHER" if p.confidence < LOW_CONFIDENCE else ""
            print(f"{s.display} ({s.lines}): {p.gender}, {p.age}{', ' + p.type if p.type else ''}, "
                  f"{p.confidence:.1f}{flag}, {p.source}: {p.note}")
    print(f"{sum(1 for s in stats if s.name in profiles)} von {len(stats)} Sprechern haben einen Steckbrief")
    return 0
```

Import `LOW_CONFIDENCE` mit: `from drova_voice.profiles import LOW_CONFIDENCE, Profile, ...`. In `HANDLERS` `"profile": _profile,` ergänzen. In `add_parsers` nach den `batches`-Zeilen:

```python
    pr = sub.add_parser("profile", help="Steckbriefe der Sprecher (casting/profiles.jsonl): Pakete für Subagents, Import, Anzeige")
    pr.add_argument("--prepare", action="store_true", help="Pakete für Subagents nach out/subagent/profile schreiben")
    pr.add_argument("--size", type=int, default=20, help="Sprecher je Paket (Standard 20)")
    pr.add_argument("--all", action="store_true", help="auch Sprecher mit Steckbrief in die Pakete aufnehmen")
    pr.add_argument("--import", dest="import_files", nargs="+", type=Path, metavar="DATEI", help="JSONL-Ergebnisse der Subagents einlesen")
    pr.add_argument("--set", metavar="NAME", help="Steckbrief von Hand setzen (braucht --gender und --age)")
    pr.add_argument("--gender", choices=["m", "f"])
    pr.add_argument("--age", choices=["kind", "jung", "mittel", "alt"])
    pr.add_argument("--type", choices=["riese", "zwerg", "schurke"])
    pr.add_argument("--note", help="ein Satz zum Charakter, ohne wörtliche Zitate")
```

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/profiles.py generator/drova_voice/pipeline.py generator/tests/test_profiles.py generator/tests/test_pipeline_profile.py
git commit -m "Add speaker profiles with import and subagent packets" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Zuteilung der Stimmen

**Files:**
- Create: `generator/drova_voice/assign.py`
- Modify: `generator/drova_voice/pipeline.py` (`_cast`, `_cast_propose`, Parser)
- Test: `generator/tests/test_assign.py` (neu), `generator/tests/test_pipeline_cast_propose.py` (neu)

**Interfaces:**
- Consumes: `Candidate` (Task 1), `Profile` (Task 5), `SpeakerStat` (Task 4), `write_auto_casting`, `tree_conflicts`, `voice_speakers` (Task 2).
- Produces: `Assignment(voices: dict[str,str], open: list[str], emergency: dict[str,str])`; `assign(stats, profiles, candidates, pinned) -> Assignment` (`pinned`: Sprecher -> Schlüssel, wird nie verändert, zählt für Last und Konflikte); `mismatch(profile, candidate) -> str | None`; `cast --propose [--keep]`, `cast --check` meldet zusätzlich Überbelegung (`--max-speakers`, Standard 12) und Szenenkonflikte.

- [ ] **Step 1: Failing tests**

`generator/tests/test_assign.py`:

```python
from collections import Counter

from drova_voice.assign import assign, mismatch
from drova_voice.fish_voices import Candidate
from drova_voice.profiles import Profile
from drova_voice.selection import SpeakerStat


def S(name, lines, *trees):
    return SpeakerStat(name, name.title(), lines, lines * 40, frozenset(trees or {f"t_{name}"}))


def P(name, gender="m", age="mittel", type=None, conf=0.9):
    return Profile(name, gender, age, type, conf, "", "llm")


ANNA = Candidate("anna", "f", "mittel", None, False)
BERTA = Candidate("berta", "f", "alt", None, False)
CARL = Candidate("carl", "m", "mittel", None, False)
CARL2 = Candidate("carl2", "m", "mittel", None, False)
DIRK = Candidate("dirk", "m", "jung", None, False)
RIESE = Candidate("riese", "m", "mittel", "riese", True)
KNABE = Candidate("knabe", "m", "kind", None, True)
ALL = [ANNA, BERTA, CARL, CARL2, DIRK, RIESE, KNABE]


def test_gender_is_a_hard_filter_and_age_decides_among_the_rest():
    r = assign([S("x", 10)], {"x": P("x", "f", "alt")}, ALL, {})
    assert r.voices == {"x": "berta"} and r.open == [] and r.emergency == {}


def test_type_match_wins_and_plain_speakers_avoid_special_variants():
    r = assign([S("giant", 20), S("plain", 10)], {"giant": P("giant", type="riese"), "plain": P("plain")}, ALL, {})
    assert r.voices["giant"] == "riese" and r.voices["plain"] == "carl"


def test_child_voices_are_reserved_for_children():
    r = assign([S("lad", 10)], {"lad": P("lad", age="jung")}, [DIRK, KNABE], {})
    assert r.voices["lad"] == "dirk"
    r = assign([S("kid", 10)], {"kid": P("kid", age="kind")}, [DIRK, KNABE], {})
    assert r.voices["kid"] == "knabe" and r.emergency == {}


def test_load_is_spread_over_equal_voices():
    stats = [S("a", 40), S("b", 30), S("c", 20), S("d", 10)]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL, CARL2], {})
    assert Counter(r.voices.values()) == {"carl": 2, "carl2": 2}


def test_speakers_sharing_a_tree_get_different_voices_when_possible():
    stats = [S("p", 20, "t1", "t2"), S("q", 10, "t2"), S("r", 5, "t9")]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL, CARL2], {})
    assert r.voices["p"] != r.voices["q"]


def test_a_single_voice_is_shared_instead_of_failing():
    stats = [S("p", 20, "t1"), S("q", 10, "t1")]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL], {})
    assert r.voices == {"p": "carl", "q": "carl"}


def test_pinned_speakers_stay_out_of_the_result_but_count_for_conflicts():
    stats = [S("p", 20, "t1"), S("q", 10, "t1")]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL, CARL2], {"p": "carl"})
    assert r.voices == {"q": "carl2"}


def test_speaker_without_a_profile_stays_open_and_nobody_else_is_affected():
    stats = [S("ghost", 50), S("x", 10)]
    r = assign(stats, {"x": P("x")}, [CARL], {})
    assert r.open == ["ghost"] and r.voices == {"x": "carl"}


def test_emergency_reports_missing_type_and_missing_child_voice():
    r = assign([S("dwarf", 9), S("girl", 8)], {"dwarf": P("dwarf", type="zwerg"), "girl": P("girl", "f", "kind")}, [CARL, ANNA], {})
    assert r.emergency == {"dwarf": "Typ 'zwerg' ohne passende Stimme", "girl": "Kind ohne Kinderstimme"}
    assert mismatch(P("o", "f", "jung"), BERTA) == "Alter weicht stark ab"
    assert mismatch(P("o", "f", "alt"), BERTA) is None


def test_assignment_is_deterministic():
    stats = [S("a", 5), S("b", 5), S("c", 5)]
    profiles = {s.name: P(s.name) for s in stats}
    assert assign(stats, profiles, ALL, {}) == assign(list(reversed(stats)), profiles, ALL, {})
```

`generator/tests/test_pipeline_cast_propose.py`:

```python
from drova_voice.cli import main


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def prepare(repo):
    (repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    run(repo, "extract")


def test_propose_writes_the_auto_file_and_check_accepts_it(pipeline_repo, capsys):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    assert run(pipeline_repo, "cast", "--propose") == 0
    assert "mira" in (pipeline_repo.casting / "casting_auto.yaml").read_text(encoding="utf-8")
    capsys.readouterr()
    assert run(pipeline_repo, "cast", "--check") == 0
    assert "lena: 2" in capsys.readouterr().out


def test_propose_reports_speakers_without_profile(pipeline_repo, capsys):
    prepare(pipeline_repo)
    assert run(pipeline_repo, "cast", "--propose") == 1
    assert "mira" in capsys.readouterr().out.lower()


def test_manual_casting_wins_and_keep_retains_the_auto_entries(pipeline_repo):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    run(pipeline_repo, "cast", "--propose")
    auto = pipeline_repo.casting / "casting_auto.yaml"
    first = auto.read_text(encoding="utf-8")
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "m", "--age", "mittel")  # Steckbrief ändert sich
    assert run(pipeline_repo, "cast", "--propose", "--keep") == 0
    assert auto.read_text(encoding="utf-8") == first  # abgenommene Besetzung bleibt
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers:\n  mira: {voice: leon}\n", encoding="utf-8")
    assert run(pipeline_repo, "cast", "--propose") == 0
    assert "mira" not in auto.read_text(encoding="utf-8").split("speakers:")[1]  # von Hand besetzt: nicht mehr in Auto


def test_check_reports_overuse_and_scene_conflicts(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers:\n  mira: {voice: lena}\n", encoding="utf-8")
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "cast", "--check", "--max-speakers", "0") == 0
    assert "Überbelegt" in capsys.readouterr().out
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_assign.py tests/test_pipeline_cast_propose.py -q`
Expected: FAIL (Modul fehlt).

- [ ] **Step 3: `generator/drova_voice/assign.py`**

```python
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from drova_voice.fish_voices import AGES, Candidate
from drova_voice.profiles import Profile
from drova_voice.selection import SpeakerStat

AGE_RANK = {age: i for i, age in enumerate(AGES)}
UNKNOWN_AGE_DISTANCE = 1  # offizielle Stimmen ohne Altersangabe passen mäßig zu jedem Alter

# Kosten (kleiner ist besser)
W_AGE = 3.0  # je Altersstufe Abstand
W_TYPE_MATCH = 10.0  # Abzug, wenn der verlangte Typ (Riese, Zwerg, Schurke) passt
W_TYPE_EXTRA = 8.0  # Aufschlag, wenn eine Typ-Variante für eine gewöhnliche Figur benutzt würde
W_KIND_ONLY = 20.0  # Kinderstimmen nur für Kinder
W_VARIANT = 2.0  # Basisstimmen vor Varianten
W_SPEAKER = 1.5  # je Sprecher, der die Stimme schon hat
W_LINES = 0.01  # je Zeile, die die Stimme schon hat
W_SHARED_TREE = 20.0  # je Dialogbaum, in dem schon jemand mit dieser Stimme spricht


@dataclass
class Assignment:
    voices: dict[str, str] = field(default_factory=dict)  # Sprecher -> Schlüssel (nur neu zugeteilte)
    open: list[str] = field(default_factory=list)  # Sprecher ohne brauchbaren Steckbrief
    emergency: dict[str, str] = field(default_factory=dict)  # Sprecher -> Grund, warum die Stimme nur Notlösung ist


class _Load:
    def __init__(self) -> None:
        self.speakers: Counter[str] = Counter()
        self.lines: Counter[str] = Counter()
        self.trees: dict[str, set[str]] = defaultdict(set)

    def add(self, key: str, stat: SpeakerStat) -> None:
        self.speakers[key] += 1
        self.lines[key] += stat.lines
        self.trees[key] |= stat.trees


def mismatch(profile: Profile, cand: Candidate) -> str | None:
    if profile.type and cand.type != profile.type:
        return f"Typ '{profile.type}' ohne passende Stimme"
    if profile.age == "kind" and cand.age != "kind":
        return "Kind ohne Kinderstimme"
    if cand.age and abs(AGE_RANK[cand.age] - AGE_RANK[profile.age]) >= 2:
        return "Alter weicht stark ab"
    return None


def _cost(profile: Profile, cand: Candidate, load: _Load, stat: SpeakerStat) -> float:
    distance = UNKNOWN_AGE_DISTANCE if cand.age is None else abs(AGE_RANK[cand.age] - AGE_RANK[profile.age])
    cost = W_AGE * distance
    if profile.type:
        if cand.type == profile.type:
            cost -= W_TYPE_MATCH
    elif cand.type:
        cost += W_TYPE_EXTRA
    if cand.age == "kind" and profile.age != "kind":
        cost += W_KIND_ONLY
    if cand.variant:
        cost += W_VARIANT
    cost += W_SPEAKER * load.speakers[cand.key] + W_LINES * load.lines[cand.key]
    cost += W_SHARED_TREE * len(stat.trees & load.trees[cand.key])
    return cost


def assign(stats: Sequence[SpeakerStat], profiles: Mapping[str, Profile], candidates: Sequence[Candidate],
           pinned: Mapping[str, str]) -> Assignment:
    """Stimmen verteilen, wichtigste Sprecher (meiste Zeilen) zuerst; `pinned` bleibt unberührt, zählt aber mit."""
    ordered = sorted(stats, key=lambda s: (-s.lines, s.name))
    by_name = {s.name: s for s in ordered}
    load = _Load()
    for name, key in pinned.items():
        if name in by_name:
            load.add(key, by_name[name])
    result = Assignment()
    for stat in ordered:
        if stat.name in pinned:
            continue
        profile = profiles.get(stat.name)
        options = [c for c in candidates if profile is not None and c.gender == profile.gender]
        if not options:
            result.open.append(stat.name)
            continue
        best = min(options, key=lambda c: (_cost(profile, c, load, stat), c.key))
        result.voices[stat.name] = best.key
        load.add(best.key, stat)
        why = mismatch(profile, best)
        if why:
            result.emergency[stat.name] = why
    return result
```

- [ ] **Step 4: `pipeline.py` anpassen**

Imports: `from drova_voice.assign import assign`, `from drova_voice.casting import cast_report, load_casting, tree_conflicts, voice_speakers, write_auto_casting`.

`_cast` ersetzen und `_cast_propose` ergänzen:

```python
def _cast(cfg: Config, args: argparse.Namespace) -> int:
    if args.propose:
        return _cast_propose(cfg, args)
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
    crowded = {v: sorted(who) for v, who in voice_speakers(lines, casting).items() if len(who) > args.max_speakers}
    if crowded:
        print("Überbelegt (mehr als %d Sprecher): " % args.max_speakers
              + "; ".join(f"{v}: {len(who)}" for v, who in sorted(crowded.items())))
    conflicts = tree_conflicts(lines, casting)
    if conflicts:
        print(f"Gleiche Stimme im selben Baum: {len(conflicts)} Fälle")
        for tree, voice, who in conflicts[:10]:
            print(f"  {tree}: {voice} ({', '.join(who)})")
    return 1 if report.missing else 0


def _cast_propose(cfg: Config, args: argparse.Namespace) -> int:
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    try:
        catalog = load_catalog(cfg.casting_dir / "fish_voices.yaml")
        manual = load_casting(cfg.casting_dir / "casting.yaml", catalog.known())
        merged = load_casting(cfg.casting_dir / "casting.yaml", catalog.known(), auto_casting_path(cfg))
        profiles = read_profiles(profiles_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    stats = speaker_stats(lines)
    kept = {n: v for n, v in merged.speakers.items() if n not in manual.speakers} if args.keep else {}
    result = assign(stats, profiles, catalog.candidates(), {**kept, **manual.speakers})
    write_auto_casting(auto_casting_path(cfg), {**kept, **result.voices})
    print(f"{len(result.voices)} Sprecher neu zugeteilt, {len(kept)} behalten, {len(manual.speakers)} von Hand besetzt "
          f"-> {auto_casting_path(cfg)}")
    display = {s.name: s.display for s in stats}
    if result.open:
        print("Offen (kein Steckbrief): " + ", ".join(display[n] for n in result.open))
    for name, why in sorted(result.emergency.items()):
        print(f"Notbesetzung {display[name]}: {why}")
    speakers_by_voice = Counter({**Counter(kept.values()), **Counter(manual.speakers.values())})
    speakers_by_voice.update(result.voices.values())
    print("Stimmen (Sprecher): " + ", ".join(f"{v}: {n}" for v, n in sorted(speakers_by_voice.items())))
    return 1 if result.open else 0
```

Imports: `from drova_voice.fish_voices import load_catalog` ist schon da; `Counter` ist importiert.

Parser: die Zeile `cast.add_argument("--check", ...)` und `cast.add_argument("--npc", ...)` bleiben; danach ergänzen:

```python
    cast.add_argument("--propose", action="store_true", help="Stimmen aus den Steckbriefen zuteilen (casting/casting_auto.yaml)")
    cast.add_argument("--keep", action="store_true", help="mit --propose: bisherige Auto-Zuteilung behalten, nur Neue zuteilen")
    cast.add_argument("--max-speakers", type=int, default=12, help="--check: ab so vielen Sprechern gilt eine Stimme als überbelegt")
```
Die `cast`-Hilfe anpassen: `help="Besetzung prüfen (--check) oder aus Steckbriefen vorschlagen (--propose)"`.

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün. Falls `test_load_is_spread_over_equal_voices` fehlschlägt, die Kostenrechnung in der Spec-Reihenfolge prüfen (a→carl, b→carl2, c→carl2, d→carl), nicht die Gewichte verbiegen.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/assign.py generator/drova_voice/pipeline.py generator/tests/test_assign.py generator/tests/test_pipeline_cast_propose.py
git commit -m "Propose voices from speaker profiles with a deterministic assignment" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Hörseite für die Besetzung

**Files:**
- Create: `generator/drova_voice/casting_sheet.py`
- Modify: `generator/drova_voice/pipeline.py`
- Test: `generator/tests/test_casting_sheet.py` (neu)

**Interfaces:**
- Consumes: `SpeakerStat`, `Profile`, `Candidate`, `Casting`, `mismatch`, `LOW_CONFIDENCE`.
- Produces: `write_casting_sheet(stats, casting, candidates, profiles, samples: Mapping[str, Line], encoded: Mapping[str, dict], audio_dir: Path, out_path: Path) -> Path`; `cast --listen` schreibt `out/casting/index.html`.

- [ ] **Step 1: Failing tests**

`generator/tests/test_casting_sheet.py`:

```python
from drova_voice.casting import Casting
from drova_voice.casting_sheet import write_casting_sheet
from drova_voice.fish_voices import Candidate
from drova_voice.lines import Line
from drova_voice.profiles import Profile
from drova_voice.selection import SpeakerStat

CANDS = [Candidate("anna", "f", "mittel", None, False), Candidate("carl", "m", "mittel", None, False)]


def sample(name, text):
    return Line(id=f"T|P|{name}", tree="T", loca_path="P", loca_key=name, node_type="statement", choice_index=None,
                actor=name.title(), category="dialog", generic=False, raw=text, speech=text, stage=(), skip=None)


def test_sheet_lists_speakers_with_voice_origin_flags_and_audio(tmp_path):
    stats = [SpeakerStat("mira", "Mira", 30, 900, frozenset({"T"})), SpeakerStat("bo", "Bo", 3, 90, frozenset({"T"})),
             SpeakerStat("cy", "Cy", 2, 60, frozenset({"T"}))]
    casting = Casting("carl", {"mira": "anna", "bo": "carl"}, frozenset({"bo"}))
    profiles = {"mira": Profile("mira", "f", "mittel", None, 0.9, "ruhig & klar", "llm"),
                "bo": Profile("bo", "m", "mittel", None, 0.3, "unsicher", "llm")}
    audio = tmp_path / "audio"
    (audio / "dialog").mkdir(parents=True)
    (audio / "dialog" / "a.ogg").write_bytes(b"x")
    samples = {"mira": sample("mira", "Ein <Satz> zum Hören."), "bo": sample("bo", "Zweiter Satz.")}
    encoded = {"T|P|mira": {"rel": "dialog/a.ogg"}}
    page = write_casting_sheet(stats, casting, CANDS, profiles, samples, encoded, audio, tmp_path / "out" / "index.html")
    html = page.read_text(encoding="utf-8")
    assert html.index("Mira") < html.index("Bo") < html.index("Cy")  # nach Zeilenzahl
    assert "<audio" in html and html.count("<audio") == 1
    assert "Ein &lt;Satz&gt; zum Hören." in html and "ruhig &amp; klar" in html
    assert "fest" in html and "auto" in html
    assert "unsicher (0.3)" in html and "kein Steckbrief" in html and "keine Stimme" in html
```

Weiterer Test in `generator/tests/test_pipeline_cast_propose.py` (anhängen):

```python
def test_listen_writes_the_sheet(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "cast", "--listen") == 0
    page = pipeline_repo.repo / "out" / "casting" / "index.html"
    assert page.is_file() and "Mira" in page.read_text(encoding="utf-8")
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_casting_sheet.py tests/test_pipeline_cast_propose.py -q`
Expected: FAIL.

- [ ] **Step 3: `generator/drova_voice/casting_sheet.py`**

```python
from __future__ import annotations

import html
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.assign import mismatch
from drova_voice.casting import Casting
from drova_voice.fish_voices import Candidate
from drova_voice.lines import Line
from drova_voice.profiles import LOW_CONFIDENCE, Profile
from drova_voice.selection import SpeakerStat

_STYLE = ("body{font:15px system-ui;margin:2rem auto;max-width:75rem;padding:0 1rem}"
          "tr:nth-child(even){background:#8881}td{padding:.4rem .6rem;vertical-align:top}"
          ".who{white-space:nowrap;font-weight:600}.meta{color:#888;font-size:.85em}.flag{color:#c60;font-size:.85em}")


def write_casting_sheet(stats: Sequence[SpeakerStat], casting: Casting, candidates: Sequence[Candidate],
                        profiles: Mapping[str, Profile], samples: Mapping[str, Line], encoded: Mapping[str, dict],
                        audio_dir: Path, out_path: Path) -> Path:
    """Hörseite zur Abnahme der Besetzung: je Sprecher Steckbrief, Stimme und eine Beispielzeile."""
    esc = html.escape
    cand = {c.key: c for c in candidates}
    rows = []
    for s in sorted(stats, key=lambda s: (-s.lines, s.name)):
        profile = profiles.get(s.name)
        voice = casting.speakers.get(s.name)
        flags = []
        if profile is None:
            flags.append("kein Steckbrief")
        elif profile.confidence < LOW_CONFIDENCE:
            flags.append(f"unsicher ({profile.confidence:.1f})")
        if voice is None:
            flags.append("keine Stimme")
        elif profile is not None and voice in cand and (why := mismatch(profile, cand[voice])):
            flags.append(why)
        origin = "" if voice is None else ("auto" if s.name in casting.auto else "fest")
        bio = "" if profile is None else (f"{profile.gender}, {profile.age}" + (f", {profile.type}" if profile.type else "")
                                          + (f"<div class='meta'>{esc(profile.note)}</div>" if profile.note else ""))
        line = samples.get(s.name)
        row = encoded.get(line.id) if line else None
        if row and (Path(audio_dir) / row["rel"]).is_file():
            audio = f'<audio controls preload="none" src="{esc((Path(audio_dir) / row["rel"]).resolve().as_uri())}"></audio>'
        else:
            audio = "<span class='meta'>noch kein Ton</span>"
        text = esc(line.speech) if line else ""
        rows.append(
            f"<tr><td class='who'>{esc(s.display)}<div class='meta'>{s.lines} Zeilen</div></td><td>{bio}</td>"
            f"<td>{esc(voice or '-')}<div class='meta'>{origin}</div></td>"
            f"<td>{audio}<div class='meta'>{text}</div></td>"
            f"<td class='flag'>{esc('; '.join(flags))}</td></tr>")
    page = (f"<!doctype html><meta charset='utf-8'><title>Besetzung</title><style>{_STYLE}</style><h1>Besetzung</h1>"
            "<p class='meta'>Korrekturen in casting/casting.yaml: <code>name: {voice: schlüssel}</code> (gewinnt gegen casting_auto.yaml).</p>"
            "<table><tr><th>Sprecher</th><th>Steckbrief</th><th>Stimme</th><th>Beispiel</th><th>Hinweis</th></tr>"
            f"{''.join(rows)}</table>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path
```

- [ ] **Step 4: `pipeline.py` anpassen**

Imports: `from drova_voice.casting_sheet import write_casting_sheet`. In `_cast` direkt nach `if args.propose: ...`:

```python
    if args.listen:
        return _cast_listen(cfg)
```

Neue Funktion:

```python
def _cast_listen(cfg: Config) -> int:
    path = lines_path(cfg)
    if not path.is_file():
        return _fail(f"{path} fehlt (zuerst `drova-voice extract` ausführen)")
    lines = read_lines(path)
    try:
        catalog, casting = _load_casting(cfg)
        profiles = read_profiles(profiles_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    samples = {l.actor.lower(): l for l in sample_lines(lines)}
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    page = write_casting_sheet(speaker_stats(lines), casting, catalog.candidates(), profiles, samples, encoded,
                               audio_dir(cfg), cfg.out_dir / "casting" / "index.html")
    heard = sum(1 for l in samples.values() if l.id in encoded)
    print(f"Hörseite: {page} ({heard} von {len(samples)} Beispielen mit Ton)")
    return 0
```

Parser: `cast.add_argument("--listen", action="store_true", help="Hörseite out/casting/index.html (nach synth/encode --sample)")`.

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/casting_sheet.py generator/drova_voice/pipeline.py generator/tests/test_casting_sheet.py generator/tests/test_pipeline_cast_propose.py
git commit -m "Add the casting listening sheet" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Abbruchregel und Zeichenverbrauch in `synth`

**Files:**
- Modify: `generator/drova_voice/synth.py`
- Modify: `generator/drova_voice/pipeline.py` (`_synth`)
- Test: `generator/tests/test_synth.py`, `generator/tests/test_pipeline_synth.py`

**Interfaces:**
- Produces: `ABORT_AFTER = 5`; `fatal_reason(error: str | None) -> str | None`; `SynthStatus(aborted: str | None = None, not_run: int = 0)`; `run_synth(..., on_result=None, status: SynthStatus | None = None)`; `pipeline.usage_path(cfg)`; `data/synth/usage.jsonl` (`at`, `engine`, `lines`, `chars`).

- [ ] **Step 1: Failing tests** (ans Ende von `generator/tests/test_synth.py`; Import oben auf `ABORT_AFTER, SynthStatus, fatal_reason` erweitern)

```python
class QuotaClient(StubClient):
    """Wie StubClient, aber Texte mit 'quota' scheitern wie bei leerem Fish-Guthaben."""

    def synth(self, req):
        if "quota" in req.text:
            with self.lock:
                self.calls.append(req.id)
            return SynthResponse(req.id, False, error="Fish lehnt die Anfrage ab (HTTP 402): Payment Required")
        return super().synth(req)


def quota_factory(calls):
    return lambda engine: contextlib.nullcontext(QuotaClient(calls))


def test_fatal_reason():
    assert fatal_reason("Fish lehnt die Anfrage ab (HTTP 402): x") == "Guthaben aufgebraucht"
    assert fatal_reason("Fish lehnt die Anfrage ab (HTTP 401): x").startswith("Anmeldung")
    assert fatal_reason("Fish nicht erreichbar nach 5 Versuchen (zuletzt HTTP 429)") == "Ratenlimit erreicht"
    assert fatal_reason("Fish nicht erreichbar nach 5 Versuchen (zuletzt TimeoutError)") == "Dienst nicht erreichbar"
    assert fatal_reason("HTTP 500") is None and fatal_reason(None) is None


def test_run_synth_aborts_after_repeated_fatal_errors_and_leaves_the_rest_untouched(tmp_path):
    calls, got, status = [], [], SynthStatus()
    jobs = [job(f"T|P|{i}", f"quota Nummer {i}.") for i in range(12)]
    results = run_synth(jobs, "fish", quota_factory(calls), tmp_path, workers=1, on_result=got.append, status=status)
    assert len(results) == ABORT_AFTER == len(got) and not any(r.ok for r in results)
    assert status.aborted == "Guthaben aufgebraucht" and status.not_run == 12 - ABORT_AFTER
    assert {r.id for r in results} == {f"T|P|{i}" for i in range(ABORT_AFTER)}  # für nicht gestartete Aufträge gibt es keine Zeilen


def test_a_success_resets_the_fatal_streak(tmp_path):
    texts = ["quota 1", "quota 2", "quota 3", "quota 4", "gut", "quota 5", "quota 6", "quota 7", "quota 8"]
    jobs = [job(f"T|P|{i}", t) for i, t in enumerate(texts)]
    status = SynthStatus()
    results = run_synth(jobs, "fish", quota_factory([]), tmp_path, workers=1, status=status)
    assert len(results) == len(texts) and status.aborted is None and status.not_run == 0
```

Ans Ende von `generator/tests/test_pipeline_synth.py`:

```python
def test_synth_records_the_characters_sent(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    first = capsys.readouterr().out
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "usage.jsonl")
    assert [r["chars"] > 0 for r in rows] == [True, False] and rows[0]["engine"] == "fake"
    assert "Zeichen neu" in first and f"insgesamt bisher: {rows[0]['chars']}" in first
```

Oben in `test_pipeline_synth.py` ist `read_jsonl_lenient` bereits importiert.

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_synth.py tests/test_pipeline_synth.py -q`
Expected: FAIL (Import).

- [ ] **Step 3: `synth.py` ändern**

Nach `MAX_ATTEMPTS = 3`:

```python
ABORT_AFTER = 5  # so viele Aufträge in Folge mit Guthaben-/Limit-/Anmeldefehler stoppen den Lauf
_FATAL = (("HTTP 402", "Guthaben aufgebraucht"), ("HTTP 401", "Anmeldung abgelehnt (API-Schlüssel prüfen)"),
          ("HTTP 403", "Zugriff verweigert"), ("HTTP 429", "Ratenlimit erreicht"),
          ("nicht erreichbar", "Dienst nicht erreichbar"))
```

Nach `class SynthResult` ergänzen:

```python
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
```

`run_synth` ersetzen:

```python
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
                        r = synth_one(client, job, key, cache_dir)
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
```

- [ ] **Step 4: `_synth` in `pipeline.py` ersetzen**

Imports: `from datetime import datetime`, `from drova_voice.synth import SynthStatus, build_jobs, run_synth`.

```python
def usage_path(cfg: Config) -> Path:
    return cfg.data_dir / "synth" / "usage.jsonl"


def _synth(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        catalog, casting = _load_casting(cfg)
        emotions = read_emotions(emotions_path(cfg))
    except (OSError, ValueError) as e:
        return _fail(str(e))
    jobs, skipped = build_jobs(lines, casting, catalog.synth_table(), emotions, args.engine)
    if args.limit:
        jobs = jobs[: args.limit]
    chars = {j.id: len(j.text) for j in jobs}
    cache_dir = cfg.cache_dir / "synth"
    path = synth_results_path(cfg)
    status = SynthStatus()
    results = run_synth(jobs, args.engine, _client_factory(cfg), cache_dir, args.workers,
                        on_result=lambda r: append_jsonl(path, r.to_dict()), status=status)
    done = [r for r in results if r.ok]
    new = [r for r in done if r.attempts > 0]
    failed = [r for r in results if not r.ok]
    flagged = [r for r in done if r.flagged]
    reasons = Counter(skipped.values())
    detail = ", ".join(f"{k}: {n}" for k, n in sorted(reasons.items())) or "keine"
    print(f"{len(done)} erzeugt ({len(done) - len(new)} aus dem Cache, {len(new)} neu erzeugt), {len(failed)} Fehler, "
          f"{len(flagged)} auffällige Dauer; übersprungen: {detail}")
    unique_new = {r.key: r for r in new}  # gleicher Text + Stimme wird nur einmal gesendet
    new_chars = sum(chars[r.id] for r in unique_new.values())
    append_jsonl(usage_path(cfg), {"at": datetime.now().isoformat(timespec="seconds"), "engine": args.engine,
                                   "lines": len(unique_new), "chars": new_chars})
    total = sum(row.get("chars", 0) for row in read_jsonl_lenient(usage_path(cfg)) if row.get("engine") == args.engine)
    print(f"Zeichen neu an {args.engine} gesendet: {new_chars}; insgesamt bisher: {total}")
    for r in failed[:10]:
        print(f"FEHLER {r.id}: {r.error}", file=sys.stderr)
    for r in flagged[:10]:
        print(f"AUFFÄLLIG {r.id}: Dauer {r.duration:.1f} s", file=sys.stderr)
    if status.aborted:
        print(f"ABBRUCH: {status.aborted}; {status.not_run} Aufträge nicht gestartet (später `synth` erneut ausführen, "
              f"Fertiges kommt aus dem Cache)", file=sys.stderr)
    return 1 if failed or status.aborted else 0
```

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/synth.py generator/drova_voice/pipeline.py generator/tests/test_synth.py generator/tests/test_pipeline_synth.py
git commit -m "Stop synth cleanly on quota or login errors and record characters sent" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Bericht je Sprecher

**Files:**
- Modify: `generator/drova_voice/report.py`
- Modify: `generator/drova_voice/pipeline.py` (`_report`, Parser)
- Test: `generator/tests/test_report.py`, `generator/tests/test_pipeline_report.py`

**Interfaces:**
- Produces: `build_speaker_report(lines, casting, synth_rows, encoded, index_entries) -> dict[str, Counter]` (Anzeigename -> Status-Zähler; ohne Barks und generische Sprecher; Spieler unter `(Spieler)`); `format_speaker_report(report, casting) -> str`; `report --by-speaker`.

- [ ] **Step 1: Failing tests** (ans Ende von `generator/tests/test_report.py`; Import oben auf `build_speaker_report, format_speaker_report` erweitern)

```python
def test_speaker_report_counts_per_speaker_and_lists_gaps():
    lines = [line("Plh_1"), line("Plh_2"), line("Plh_3", skip="gvar"), line("Plh_4", actor="Fremder"),
             line("Plh_5", actor="Player", category="player"), line("Plh_6", category="bark")]
    index = {"T|P|Plh_1": {}}
    report = build_speaker_report(lines, CASTING, {}, {}, index)
    assert report["Mira"] == {"installiert": 1, "offen": 1, "übersprungen: gvar": 1}
    assert report["Fremder"] == {"übersprungen: no_voice": 1}
    assert report["(Spieler)"] == {"offen": 1}
    assert "Plh_6" not in str(report) and len(report) == 3
    text = format_speaker_report(report, CASTING)
    assert "Mira (lena): 3 Zeilen" in text and "1 installiert" in text and "1 offen" in text
    assert "Lücken: 2 Zeilen bei 2 Sprechern" in text
```

Ans Ende von `generator/tests/test_pipeline_report.py` (Datei zuerst ansehen und deren `run`-Hilfe benutzen; falls keine existiert, `main(["--config", str(pipeline_repo.cfg), ...])`):

```python
def test_report_by_speaker(pipeline_repo, capsys):
    from drova_voice.cli import main
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "report", "--by-speaker"]) == 0
    out = capsys.readouterr().out
    assert "Mira (lena)" in out and "Lücken" in out
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_report.py tests/test_pipeline_report.py -q`
Expected: FAIL (Import).

- [ ] **Step 3: `report.py` ergänzen** (am Ende der Datei)

```python
GAP_STATUSES = ("kodiert", "erzeugt", "fehler", "offen")


def build_speaker_report(lines: Sequence[Line], casting: Casting, synth_rows: Mapping[str, dict],
                         encoded: Mapping[str, dict], index_entries: Mapping[str, dict]) -> dict[str, Counter]:
    """Status je Sprecher; Barks und generische Sprecher gehören nicht zu Plan 5."""
    result: dict[str, Counter] = {}
    for line in lines:
        if line.category == "bark" or line.generic:
            continue
        who = "(Spieler)" if line.category == "player" else line.actor
        result.setdefault(who, Counter())[_status(line, casting, synth_rows, encoded, index_entries)] += 1
    return result


def format_speaker_report(report: Mapping[str, Counter], casting: Casting) -> str:
    def total(counts: Counter) -> int:
        return sum(counts.values())

    out = []
    gap_lines = gap_speakers = 0
    for who in sorted(report, key=lambda w: (-total(report[w]), w)):
        counts = report[who]
        voice = casting.default_player if who == "(Spieler)" else casting.speakers.get(who.lower())
        parts = [f"{counts[k]} {k}" for k in ORDER if counts[k]]
        parts += [f"{n} {k}" for k, n in sorted(counts.items()) if k.startswith("übersprungen")]
        out.append(f"{who} ({voice or 'keine Stimme'}): {total(counts)} Zeilen -> " + ", ".join(parts))
        gaps = sum(counts[k] for k in GAP_STATUSES)
        if gaps:
            gap_lines += gaps
            gap_speakers += 1
    out.append(f"Lücken: {gap_lines} Zeilen bei {gap_speakers} Sprechern (nicht installiert, nicht übersprungen)")
    return "\n".join(out)
```

- [ ] **Step 4: `pipeline.py` anpassen**

Imports: `from drova_voice.report import build_report, build_speaker_report, format_report, format_speaker_report`. In `_report` den Block ab `statuses = ...` ersetzen:

```python
    synth_rows = latest_by_id(read_jsonl_lenient(synth_results_path(cfg)))
    encoded = latest_by_id(read_jsonl_lenient(encoded_path(cfg)))
    if args.by_speaker:
        print(format_speaker_report(build_speaker_report(lines, casting, synth_rows, encoded, entries), casting))
        return 0
    print(format_report(build_report(lines, casting, synth_rows, encoded, entries)))
    return 0
```

Parser: nach `_add_selection(rp)`: `rp.add_argument("--by-speaker", action="store_true", help="Status je Sprecher statt je Kategorie")`.

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/report.py generator/drova_voice/pipeline.py generator/tests/test_report.py generator/tests/test_pipeline_report.py
git commit -m "Report progress per speaker" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Emotionen für alle Zeilen (Pakete und Import)

**Files:**
- Modify: `generator/drova_voice/emote.py`
- Modify: `generator/drova_voice/pipeline.py` (`_emote`, Parser)
- Test: `generator/tests/test_emote.py`, `generator/tests/test_pipeline_emote.py`

**Interfaces:**
- Consumes: `Profile` (Task 5), `EmotionTag`, `Event` (`drova_voice.emotions`).
- Produces: `prepare_emote_packets(lines, profiles, trees_per_packet=20) -> list[list[dict]]`; `ImportResult(merged, imported, kept, errors)` und `import_llm_emotions(existing, rows, valid_ids) -> ImportResult`; `emote --prepare [--size N]`, `emote --import DATEI...`.

- [ ] **Step 1: Failing tests** (ans Ende von `generator/tests/test_emote.py`; Imports oben: `from drova_voice.emote import import_llm_emotions, prepare_emote_packets`, `from drova_voice.emotions import EmotionTag`, `from drova_voice.lines import Line`, `from drova_voice.profiles import Profile`; falls diese Importe schon existieren, nicht doppeln)

```python
def eline(key, actor="Anna", speech="Hallo da.", tree="T1", category="dialog", skip=None, stage=()):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw=speech, speech="" if skip else speech, stage=stage, skip=skip)


def test_prepare_emote_packets_hold_whole_trees_with_speaker_profiles():
    lines = [eline("1", "Anna", stage=({"text": "seufzt", "pos": 0},)), eline("2", "Bob"), eline("3", "Anna", tree="T2"),
             eline("4", "Cy", skip="gvar"), eline("5", "Cy", category="bark", tree="T3"),
             eline("6", "Player", category="player", tree="T2")]
    profiles = {"anna": Profile("anna", "f", "mittel", None, 0.9, "ruhig", "llm")}
    packets = prepare_emote_packets(lines, profiles, trees_per_packet=1)
    assert [[t["tree"] for t in p] for p in packets] == [["T1"], ["T2"]]
    t1 = packets[0][0]
    assert [(l["id"], l["actor"], l["stage"]) for l in t1["lines"]] == [("T1|P|1", "Anna", ["seufzt"]), ("T1|P|2", "Bob", [])]
    assert t1["speakers"] == {"anna": {"gender": "f", "age": "mittel", "note": "ruhig"}}


def test_import_llm_emotions_rules():
    existing = {"T|P|1": EmotionTag("sad", 0.5, source="manual"), "T|P|2": EmotionTag("angry", 0.6, source="stage"),
                "T|P|3": EmotionTag("tender", 0.4, source="llm")}
    rows = [{"id": "T|P|1", "emotion": "joyful", "intensity": 0.7},
            {"id": "T|P|2", "emotion": "joyful", "intensity": 0.7},
            {"id": "T|P|3", "emotion": "stern", "intensity": 0.5, "source": "manual"},
            {"id": "T|P|4", "emotion": "excited", "intensity": 0.8, "events": [{"tag": "laugh", "pos": 3}]},
            {"id": "T|P|9", "emotion": "joyful", "intensity": 0.7},
            {"id": "T|P|5", "emotion": "wütend", "intensity": 0.7}]
    r = import_llm_emotions(existing, rows, {"T|P|1", "T|P|2", "T|P|3", "T|P|4", "T|P|5"})
    assert r.merged["T|P|1"].source == "manual" and r.merged["T|P|2"].source == "stage"
    assert r.merged["T|P|3"].emotion == "stern" and r.merged["T|P|3"].source == "llm"
    assert r.merged["T|P|4"].events[0].tag == "laugh" and r.merged["T|P|4"].source == "llm"
    assert (r.imported, r.kept) == (2, 2) and len(r.errors) == 2
    assert any("T|P|9" in e for e in r.errors) and any("T|P|5" in e for e in r.errors)
```

Ans Ende von `generator/tests/test_pipeline_emote.py`:

```python
import json


def test_emote_prepare_and_import(pipeline_repo, tmp_path, capsys):
    cfg = str(pipeline_repo.cfg)
    main(["--config", cfg, "extract"])
    assert main(["--config", cfg, "emote", "--prepare"]) == 0
    packet = json.loads((pipeline_repo.repo / "out" / "subagent" / "emote" / "packet_001.json").read_text(encoding="utf-8"))
    assert packet[0]["tree"] == "DT_Test_NPC_Mira" and len(packet[0]["lines"]) == 3
    incoming = tmp_path / "result.jsonl"
    incoming.write_text(json.dumps({"id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2", "emotion": "tender", "intensity": 0.6}) + "\n"
                        + json.dumps({"id": "gibt|es|nicht", "emotion": "sad", "intensity": 0.5}) + "\n", encoding="utf-8")
    assert main(["--config", cfg, "emote", "--import", str(incoming)]) == 1
    assert "gibt|es|nicht" in capsys.readouterr().err
    emotions = read_emotions(pipeline_repo.casting / "emotions.jsonl")
    assert emotions["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2"].source == "llm"
```

Die drei Zeilen des Mira-Baums im Fixture: Plh_1 (Mira), Plh_2 (Mira), Plh_3 (Spieler-Aussage); Plh_4 (gvar) und Plh_5 (unsprechbar) sind übersprungen, Plh_6 ist Auswahloption.

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_emote.py tests/test_pipeline_emote.py -q`
Expected: FAIL (Import).

- [ ] **Step 3: `emote.py` ergänzen** (Imports oben erweitern um `from dataclasses import dataclass`, `from drova_voice.profiles import Profile`; ans Ende der Datei)

```python
@dataclass
class ImportResult:
    merged: dict[str, EmotionTag]
    imported: int
    kept: int  # manual- und stage-Zeilen bleiben, wie sie sind
    errors: list[str]


def prepare_emote_packets(lines: Sequence[Line], profiles: Mapping[str, Profile],
                          trees_per_packet: int = 20) -> list[list[dict]]:
    """Pakete für Subagents: je Dialogbaum alle sprechbaren Zeilen am Stück plus Steckbriefe der Sprecher."""
    by_tree: dict[str, list[Line]] = {}
    for line in lines:
        if not line.skip and line.category != "bark":
            by_tree.setdefault(line.tree, []).append(line)
    trees = []
    for tree in sorted(by_tree):
        speakers = {}
        for line in by_tree[tree]:
            p = profiles.get(line.actor.lower())
            if p is not None:
                speakers[p.speaker] = {"gender": p.gender, "age": p.age, "note": p.note}
        trees.append({"tree": tree, "speakers": speakers,
                      "lines": [{"id": l.id, "actor": l.actor, "text": l.speech, "stage": [s["text"] for s in l.stage]}
                                for l in by_tree[tree]]})
    return [trees[i:i + trees_per_packet] for i in range(0, len(trees), trees_per_packet)]


def import_llm_emotions(existing: Mapping[str, EmotionTag], rows: Sequence[Mapping], valid_ids: set[str]) -> ImportResult:
    """LLM-Zeilen übernehmen: Quelle wird llm, manual und stage (feste Signale) bleiben, unbekannte IDs werden gemeldet."""
    merged = dict(existing)
    imported = kept = 0
    errors: list[str] = []
    for number, row in enumerate(rows, start=1):
        line_id = row.get("id")
        if line_id not in valid_ids:
            errors.append(f"Zeile {number}: unbekannte ID {line_id!r}")
            continue
        try:
            tag = EmotionTag.from_dict({**row, "source": "llm"})
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"Zeile {number} ({line_id}): {e}")
            continue
        if line_id in merged and merged[line_id].source in ("manual", "stage"):
            kept += 1
            continue
        merged[line_id] = tag
        imported += 1
    return ImportResult(merged, imported, kept, errors)
```

- [ ] **Step 4: `pipeline._emote` und Parser**

Imports: `from drova_voice.emote import import_llm_emotions, merge_emotions, prepare_emote_packets, read_emotions, write_emotions`.

```python
def _emote(cfg: Config, args: argparse.Namespace) -> int:
    lines = _selected(cfg, args)
    if lines is None:
        return 2
    try:
        existing = read_emotions(emotions_path(cfg))
        profiles = read_profiles(profiles_path(cfg))
    except ValueError as e:
        return _fail(str(e))
    if args.prepare:
        packets = prepare_emote_packets(lines, profiles, args.size)
        out = cfg.out_dir / "subagent" / "emote"
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("packet_*.json"):
            old.unlink()
        for i, packet in enumerate(packets, start=1):
            (out / f"packet_{i:03d}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{sum(len(p) for p in packets)} Dialogbäume in {len(packets)} Paketen -> {out}")
        return 0
    if args.import_files:
        rows = [row for f in args.import_files for row in read_jsonl_lenient(f)]
        result = import_llm_emotions(existing, rows, {l.id for l in lines if not l.skip})
        write_emotions(emotions_path(cfg), result.merged)
        print(f"{result.imported} LLM-Emotionen übernommen, {result.kept} feste Zeilen behalten -> {emotions_path(cfg)}")
        for e in result.errors[:20]:
            print(f"FEHLER {e}", file=sys.stderr)
        return 1 if result.errors else 0
    merged = merge_emotions(existing, lines)
    write_emotions(emotions_path(cfg), merged)
    sources = Counter(t.source for t in merged.values())
    print(f"{len(merged)} Emotionen -> {emotions_path(cfg)}; " + ", ".join(f"{s}: {n}" for s, n in sorted(sources.items())))
    return 0
```

Parser: nach `em.add_argument("--npc", ...)` durch `_add_selection(em)` ersetzen (die Zeile `em.add_argument("--npc", help="nur Bäume, in denen dieser NPC spricht")`), danach:

```python
    em.add_argument("--prepare", action="store_true", help="Dialogbäume als Pakete für Subagents nach out/subagent/emote schreiben")
    em.add_argument("--size", type=int, default=20, help="Dialogbäume je Paket (Standard 20)")
    em.add_argument("--import", dest="import_files", nargs="+", type=Path, metavar="DATEI", help="JSONL-Ergebnisse der Subagents einlesen")
```

- [ ] **Step 5: Alle Tests**

Run: `cd generator && .venv/Scripts/python -m pytest -q 2>&1 | tail -3`
Expected: grün.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/emote.py generator/drova_voice/pipeline.py generator/tests/test_emote.py generator/tests/test_pipeline_emote.py
git commit -m "Prepare subagent packets and import LLM emotions" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Dokumentation

**Files:**
- Modify: `docs/generator.md`

- [ ] **Step 1: Abschnitt „Plan 5“ in `docs/generator.md` ergänzen** (nach der Tabelle „Reihenfolge“; die Grenzen-Liste um die neuen Punkte anpassen: „Keine Varianten für generische Sprecher“ bleibt; „Die Stimmenzuordnung ... vorläufig“ ersetzen durch „Besetzung: `casting/casting.yaml` (von Hand, gewinnt) über `casting/casting_auto.yaml` (erzeugt)“)

```markdown
## Casting und Vollauf (Plan 5)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| a | `profile --prepare` | Pakete mit Sprecherauszügen unter `out/subagent/profile/` (enthalten Spieltexte, nie ins Git) |
| b | `profile --import <Dateien>` | prüft die JSONL-Ergebnisse der Subagents und schreibt `casting/profiles.jsonl` (`manual`-Zeilen bleiben) |
| c | `profile --set NAME --gender m --age mittel [--type riese] [--note ...]` / `profile` | Steckbrief von Hand setzen / Prüfliste (unsichere Einträge markiert) |
| d | `cast --propose [--keep]` | `casting/casting_auto.yaml`; `casting.yaml` gewinnt; `--keep` lässt die bisherige Auto-Zuteilung stehen |
| e | `synth --sample`, `encode --sample`, `cast --listen` | Hörseite `out/casting/index.html`, eine Beispielzeile je Sprecher |
| f | `emote --prepare`, `emote --import <Dateien>` | LLM-Emotionen für alle Dialogbäume (`stage`- und `manual`-Zeilen bleiben) |
| g | `batches [--max-chars N]` | Etappen nach Wichtigkeit in `data/batches.json` |
| h | `synth --batch N`, `encode --batch N`, `install --batch N` | eine Etappe erzeugen; `synth` bricht bei Guthaben-/Limit-/Anmeldefehlern nach 5 Fehlern in Folge sauber ab |
| i | `report --by-speaker` | Status und Lücken je Sprecher |

`--sample` und `--batch N` gelten für `synth`, `encode`, `install`, `report` und `preview`. Varianten (`voice: alte_frau` in `casting.yaml`) werden mit der Basisstimme erzeugt und beim Kodieren per ffmpeg (`rubberband`) umgeformt. Der Zeichenverbrauch je Lauf steht am Ende der `synth`-Ausgabe und in `data/synth/usage.jsonl`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/generator.md
git commit -m "Document the casting and batch commands" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Operationen (mit dem Nutzer, kein Code)

Diese Aufgaben laufen in der Hauptsitzung. **Vor jedem Schritt, der Spieltexte an einen Dienst schickt, fragt die Hauptsitzung ausdrücklich nach einem Ja und nennt, was gesendet wird.** Voraussetzung: Tasks 0 bis 11 sind fertig und grün; `data/lines.jsonl` ist aktuell (sonst `drova-voice extract`).

### Task 12: Steckbriefe der Sprecher

- [ ] **Step 1: Pakete bauen**

```bash
cd /d/Games/Projekte/DrovaTTAI/generator && .venv/Scripts/drova-voice profile --prepare
```
Expected: `246 Sprecher in 13 Paketen -> .../out/subagent/profile`.

- [ ] **Step 2: Freigabe einholen.** Fragen: „Darf ich je Paket (20 Sprecher, jeweils Auszüge ihrer Zeilen und Zeilen, die sie erwähnen, zusammen rund 100.000 Zeichen) an einen Haiku-Subagenten schicken? Er schreibt nur eine JSONL-Datei unter `out/subagent/profile/`.“ Auf klares Ja warten.

- [ ] **Step 3: Subagents starten** (nach Ja; Modell `haiku`, höchstens vier gleichzeitig, je Paket ein Auftrag `packet_NNN.json` → `result_NNN.jsonl`, beide unter `out/subagent/profile/`). Auftragstext:

> Du bekommst die Datei `<Pfad>/packet_NNN.json`: eine Liste von Sprechern aus dem Spiel „Drova – Forsaken Kin“ (deutsche Fantasy-Dialoge). Je Eintrag: `speaker` (Schlüssel), `display` (Name), `lines` (Zeilenzahl), `trees`, `own` (Auszug seiner Zeilen), `mentions` (Zeilen anderer, die ihn nennen). Bestimme je Sprecher: `gender` (`m` oder `f`) aus Anrede, Pronomen in `mentions`, Rolle und Sprechweise, **nie allein aus dem Namen**; `age` (`kind`, `jung`, `mittel` oder `alt`); `type` (`riese`, `zwerg`, `schurke` oder leer, nur wenn eindeutig erkennbar); `confidence` (0 bis 1; bei dünnen Hinweisen höchstens 0.4, aber trotzdem die beste Schätzung); `note` (ein Satz zum Charakter, höchstens 120 Zeichen, **keine wörtlichen Zitate**). Schreibe genau eine JSON-Zeile je Sprecher nach `<Pfad>/result_NNN.jsonl`: `{"speaker": "<Schlüssel>", "gender": "m", "age": "mittel", "type": "", "confidence": 0.8, "note": "..."}`. Keine anderen Dateien ändern, keine Erklärung ausgeben, nur die Datei schreiben.

- [ ] **Step 4: Importieren und prüfen**

```bash
.venv/Scripts/drova-voice profile --import ../out/subagent/profile/result_*.jsonl
.venv/Scripts/drova-voice profile
```
Fehlende oder abgelehnte Sprecher (Importfehler) mit einem erneuten Paket (`profile --prepare` baut nur die ohne Steckbrief) wiederholen. Danach zeigt der Nutzer die Prüfliste (`profile`, besonders `UNSICHER`-Zeilen); Korrekturen mit `profile --set NAME --gender ... --age ...`. Dabei auch die sechs bisher besetzten Sprecher prüfen (Femke ist ein Mann).

- [ ] **Step 5: Commit**

```bash
cd /d/Games/Projekte/DrovaTTAI && git add casting/profiles.jsonl
git commit -m "Add the LLM speaker profiles reviewed by the user" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

### Task 13: Besetzung vorschlagen und anhören

- [ ] **Step 1: Zuteilung**

```bash
cd generator && .venv/Scripts/drova-voice cast --propose && .venv/Scripts/drova-voice cast --check
```
Notbesetzungen, offene Sprecher, Überbelegung und Szenenkonflikte dem Nutzer nennen; Steckbriefe oder `casting.yaml` nachbessern, `cast --propose` wiederholen (ohne `--keep`, solange noch niemand abgenommen hat).

- [ ] **Step 2: Freigabe für die Hörstufe einholen.** Nenne Anzahl der Beispielzeilen (`synth --sample --limit` nicht nötig, ~246 Zeilen, rund 20.000 Zeichen) und dass sie an `api.fish.audio` (Modell `s2.1-pro-free`) gehen. Der Nutzer nennt den Fish-Key im Chat; er steht nur im Einzelbefehl.

- [ ] **Step 3: Beispiele erzeugen** (nach Ja)

```bash
FISH_API_KEY='<Schlüssel>' .venv/Scripts/drova-voice synth --sample
.venv/Scripts/drova-voice encode --sample
.venv/Scripts/drova-voice cast --listen
```
Die Hörseite `out/casting/index.html` öffnen (Datei im Browser). Der Nutzer hört, nennt Korrekturen; sie kommen in `casting/casting.yaml` (`name: {voice: schlüssel}`, Varianten wie `alte_frau` sind erlaubt). Nach Korrekturen `synth --sample`, `encode --sample`, `cast --listen` wiederholen (nur geänderte Zeilen kosten neu).

- [ ] **Step 4: Abnahme festhalten**

Der Nutzer nimmt die Besetzung ab. Danach nur noch `cast --propose --keep` benutzen. Commit:

```bash
cd /d/Games/Projekte/DrovaTTAI && git add casting/casting.yaml casting/casting_auto.yaml casting/profiles.jsonl
git commit -m "Record the user-approved casting" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

### Task 14: Emotionen für alle Zeilen

- [ ] **Step 1: Regeln anwenden und Pakete bauen**

```bash
cd generator && .venv/Scripts/drova-voice emote && .venv/Scripts/drova-voice emote --prepare
```
Expected: `1405 Dialogbäume ...` (Zahl kann leicht abweichen) in rund 70 Paketen.

- [ ] **Step 2: Freigabe einholen.** Fragen: „Darf ich je Paket (20 Dialogbäume, alle Zeilen am Stück plus Steckbriefe) an einen Haiku-Subagenten schicken? Insgesamt rund 850.000 Zeichen Dialogtext; er schreibt nur JSONL-Dateien unter `out/subagent/emote/`.“ Auf Ja warten.

- [ ] **Step 3: Subagents** (nach Ja; Modell `haiku`, höchstens vier gleichzeitig; je Paket `packet_NNN.json` → `result_NNN.jsonl`). Auftragstext:

> Du bekommst `<Pfad>/packet_NNN.json`: Dialogbäume aus „Drova – Forsaken Kin“. Je Baum die Zeilen in Reihenfolge (`id`, `actor`, `text`, `stage` = Regieanweisungen) und Steckbriefe der Sprecher. Gib nur für Zeilen, in denen eine Emotion **klar im Text** steht, genau eine JSON-Zeile nach `<Pfad>/result_NNN.jsonl` aus: `{"id": "<ID>", "emotion": "<angry|contemplative|excited|joyful|mundane|nervous|sad|stern|surprised|tender>", "intensity": <0.0-1.0>, "events": [], "emphasis": [], "notes": []}`. Regeln: Zurückhaltung, der Standard ist neutral und diese Zeilen gibst du **nicht** aus; Zeilen, deren `stage` schon eine Emotion nennt, überspringst du; `events` bleiben leer, außer der Text nennt den Laut ausdrücklich (erlaubt: gasp, giggle, growl, gulp, laugh, pause, scoff, sigh, sob, um, mit `pos` als Zeichenindex); höchstens ein Wort in `emphasis`. Nichts anderes ausgeben, keine Texte wiederholen.

- [ ] **Step 4: Importieren**

```bash
.venv/Scripts/drova-voice emote --import ../out/subagent/emote/result_*.jsonl
```
Importfehler ansehen (unbekannte IDs, ungültige Emotionen) und betroffene Pakete bei Bedarf wiederholen. Stichprobe mit `preview --npc <Name>`.

- [ ] **Step 5: Commit**

```bash
cd /d/Games/Projekte/DrovaTTAI && git add casting/emotions.jsonl
git commit -m "Add LLM emotions for all dialog trees" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

### Task 15: Etappen erzeugen und installieren

- [ ] **Step 1: Etappen planen und dem Nutzer zeigen**

```bash
cd generator && .venv/Scripts/drova-voice batches
```
Erwartet rund neun Etappen. Nenne dem Nutzer Zeichen je Etappe und die Summe.

- [ ] **Step 2: Je Etappe N (1, 2, ...) wiederholen:**

  1. Ausdrückliches Ja für diese Etappe einholen (Sprecher, Zeilen, Zeichen; Ziel `api.fish.audio`; Key vom Nutzer, nur im Einzelbefehl).
  2. ```bash
     FISH_API_KEY='<Schlüssel>' .venv/Scripts/drova-voice synth --batch N
     .venv/Scripts/drova-voice encode --batch N
     .venv/Scripts/drova-voice install --batch N
     .venv/Scripts/drova-voice report --by-speaker
     ```
  3. Bei `ABBRUCH:` (Guthaben, Limit, Anmeldung) nicht weiterlaufen lassen, dem Nutzer Grund und bisherigen Verbrauch (`insgesamt bisher`) nennen und die Tarifentscheidung abwarten; danach `synth --batch N` erneut (Fertiges kommt aus dem Cache). Bei `AUFFÄLLIG` oder `FEHLER`: betroffene WAVs löschen und `synth` wiederholen (siehe `docs/generator.md`).
  4. Nach Etappe 1 und nach der letzten: Der Nutzer hört im Spiel stichprobenartig (Spiel vorher schließen, es lädt `index.json` beim Start).

- [ ] **Step 3: Abschlussbericht**

```bash
.venv/Scripts/drova-voice report --by-speaker | tail -5
```
Erfolgskriterium: `Lücken: 0 Zeilen` (außer Sprechern ohne Zeilen im Plan-Umfang) und alle Etappen installiert.

### Task 16: Abschluss

- [ ] **Step 1: Notiz zum Ergebnis** in `docs/decisions/2026-10-casting-vollauf.md` (nur Zahlen und Entscheidungen, keine Spieltexte): Zahl Sprecher, Zeichenverbrauch (`data/synth/usage.jsonl`), gewählter Fish-Tarif, Notbesetzungen, Ergebnis der Stichprobe im Spiel.

- [ ] **Step 2: `docs/HANDOFF.md` aktualisieren** (Stand-Tabelle: Plan 5 fertig; Stimmenzuordnung; nächste Schritte: Mod-Ausbau, generische Sprecher, Merge/Historie/Lizenz), und die Gedächtnisdatei `plan-5-status.md` samt Zeile in `MEMORY.md` anlegen.

- [ ] **Step 3: Commit**

```bash
cd /d/Games/Projekte/DrovaTTAI && git add docs/decisions/2026-10-casting-vollauf.md docs/HANDOFF.md
git commit -m "Record the result of the full run and update the handoff" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4:** Mit dem Nutzer klären, ob Merge oder PR (`superpowers:finishing-a-development-branch`). Nichts pushen ohne Ja.
