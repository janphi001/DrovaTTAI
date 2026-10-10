# DrovaVoice – Plan 1: Fundament & Hörtest

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fundament von DrovaVoice bauen (Python-Generator-Kern, C#-Kern, leerer Mod im Spiel) und den TTS-Hörtest (M2) so weit bringen, dass der Nutzer Engine und Stimmen-Quelle wählen kann.

**Architecture:** Python-CLI `drova-voice` mit reiner, getesteter Textlogik (`.loc`-Parser, Sprechtext, Spielername, Emotionen, Engine-Rendering) und einem JSON-Lines-Protokoll zu Engine-Workern, die je in eigener venv laufen. C#-Bibliothek `DrovaVoice.Core` bildet Zeilen-IDs identisch zu Python (gemeinsame Testvektoren). Der MelonLoader-Mod `DrovaVoice` ist in diesem Plan nur ein Gerüst, das im Spiel lädt.

**Tech Stack:** Python 3.12 (uv, pytest, pyyaml, num2words), Worker-venvs Python 3.11 (torch 2.6 cu124, kittenml, chatterbox-tts, coqui-tts), .NET 6 (Mod/Core), .NET 8 (xUnit-Tests), MelonLoader 0.7.3, Drova Modding API 0.5.4.

**Spec:** `docs/superpowers/specs/2026-10-10-drova-voice-design.md`

**Nicht in diesem Plan** (folgen als Plan 2+ nach den Ergebnissen von M0/M2): Export-Mod (M1), Wiedergabe (M3), Casting/Emotion-Batches, Generierung aller Zeilen, Barks, Briefe, Laufzeit-TTS.

## Global Constraints

- Keine Spieltexte und kein Audio im Git: `data/`, `cache/`, `out/`, `voices/`, `generator/config.yaml` sind gitignored.
- Generator: Python ≥ 3.11, eigene venv unter `generator/.venv` (uv). Jede TTS-Engine hat **eigene** venv unter `generator/workers/<engine>/.venv`.
- Zeilen-ID: Aussage `{tree}|{locaPath}|{locaKey}`, Auswahl `…|c{choiceIndex}`, Variante `#{variant}`; `locaPath` mit `/` normalisiert, führende/abschließende `/` entfernt. Audio-Dateiname = erste 16 Hex-Zeichen von SHA-1(UTF-8(volle ID)) + `.ogg`. Python und C# müssen `tests/vectors/line_ids.json` erfüllen.
- Emotionen ∈ {neutral, angry, contemplative, excited, joyful, mundane, nervous, sad, stern, surprised, tender}; Laute ∈ {gasp, giggle, growl, gulp, laugh, pause, scoff, sigh, sob, um}.
- Spielername: Platzhalter `$GVAR:EVars_Player.Name$`, Standardname „Arden“.
- C#-Mod: `net6.0`, MelonLoader ≥ 0.7.0; `DrovaVoice.Core` ohne Il2Cpp-/Unity-Abhängigkeit.
- Spielpfad: `D:\Games\Steam\steamapps\common\Drova - Forsaken Kin` (überschreibbar per `DROVA_GAME_DIR` bzw. `config.yaml`).
- **Downloads/Installationen ins System oder den Spielordner (Modelle, torch, MelonLoader, API) erst nach ausdrücklicher Freigabe des Nutzers** (Dateiname, Quelle, Größe nennen).
- Jeder Commit endet mit der Zeile `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Code-Bezeichner Englisch, Nutzer-Meldungen (CLI/Log) Deutsch.

## Review Focus

1. `.loc`-Dateien mit BOM, CRLF oder mehrzeiligen Einträgen → müssen korrekt geparst werden, ohne Einträge zu verschlucken (Tests in Task 4).
2. Zeilen, die nach Entfernen der Regieanweisungen leer sind (z. B. nur `*grinst*`) → dürfen nie an eine Engine gehen (Tests in Task 5 und Task 10).
3. TTS-Bibliotheken schreiben Log-Text auf stdout → darf das Worker-Protokoll nicht zerstören (Test mit lärmendem Fake-Worker in Task 9).
4. Umlaute in Baum-/Pfadnamen → Python und C# müssen denselben Hash bilden (Vektor 4 in Task 2 und Task 3).
5. Hörtest bricht mittendrin ab (Absturz, Strg+C) → halbe Dateien dürfen nicht als fertig gelten, Neustart setzt fort (Test in Task 11).

## Dateistruktur (dieser Plan)

```
.gitignore                                   Task 1
README.md                                    Task 1
tests/vectors/line_ids.json                  Task 2   gemeinsame ID-Vektoren
generator/pyproject.toml                     Task 1
generator/config.example.yaml                Task 1
generator/bakeoff_voices.yaml                Task 11
generator/drova_voice/__init__.py            Task 1
generator/drova_voice/config.py              Task 1   Config laden
generator/drova_voice/ids.py                 Task 2   Zeilen-IDs, Dateinamen
generator/drova_voice/loc.py                 Task 4   .loc-Parser
generator/drova_voice/speech_text.py         Task 5   Sprechtext
generator/drova_voice/player_name.py         Task 6   Namensvarianten
generator/drova_voice/emotions.py            Task 7   Emotionsmodell + Regieanweisungen
generator/drova_voice/render.py              Task 8   Engine-spezifisches Rendering
generator/drova_voice/jsonl.py               Task 10  JSONL-Helfer
generator/drova_voice/engines/__init__.py    Task 9
generator/drova_voice/engines/protocol.py    Task 9   SynthRequest/SynthResponse
generator/drova_voice/engines/client.py      Task 9   EngineClient, worker_command
generator/drova_voice/bakeoff.py             Task 10/11 Auswahl, Lauf, Hörseite
generator/drova_voice/cli.py                 Task 11  CLI
generator/workers/_common/worker_loop.py     Task 9
generator/workers/fake/worker.py             Task 9   stdlib-Fake für Tests
generator/workers/kitten/{worker.py,requirements.txt,README.md}      Task 12
generator/workers/chatterbox/{worker.py,requirements.txt,README.md}  Task 12
generator/workers/xtts/{worker.py,requirements.txt,README.md}        Task 12
generator/tests/test_*.py                    je Task
mod/Directory.Build.props                    Task 3
mod/DrovaVoice.sln                           Task 3
mod/DrovaVoice.Core/DrovaVoice.Core.csproj   Task 3
mod/DrovaVoice.Core/LineIds.cs               Task 3
mod/DrovaVoice.Core.Tests/…                  Task 3
mod/DrovaVoice/DrovaVoice.csproj             Task 15
mod/DrovaVoice/DrovaVoiceMod.cs              Task 15
docs/decisions/2026-10-tts-engine.md         Task 13
docs/setup.md                                Task 14
```

**Reihenfolge/Parallelität:** Tasks 1→2→4→5→6→7→8→9→10→11 (Python, sequenziell). Task 3 (C#) nach Task 2 parallel möglich. Tasks 14→15 (Spiel) parallel zu allem, interaktiv mit dem Nutzer. Task 12 nach 9 und Freigabe, Task 13 nach 11 und 12.

Alle Befehle laufen in Git Bash ab Repo-Wurzel `D:\Games\Projekte\DrovaTTAI`, sofern nicht anders angegeben.

---

### Task 1: Repo-Gerüst und Config

**Files:**
- Create: `.gitignore`, `README.md` (überschreiben), `generator/pyproject.toml`, `generator/config.example.yaml`, `generator/drova_voice/__init__.py`, `generator/drova_voice/config.py`
- Test: `generator/tests/test_config.py`

**Interfaces:**
- Produces: `drova_voice.config.Config` (frozen dataclass: `game_dir: Path`, `language: str`, `repo_root: Path`; Properties `loc_dir`, `data_dir`, `out_dir`, `voices_dir`, `workers_dir`), `drova_voice.config.load_config(path: Path) -> Config`, `drova_voice.config.DEFAULT_CONFIG_PATH: Path`

- [ ] **Step 1: Gerüst-Dateien anlegen**

`.gitignore`:
```gitignore
# Spielabgeleitete Daten und erzeugtes Audio – niemals committen
data/
cache/
out/
voices/
generator/config.yaml

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/

# .NET
bin/
obj/
*.user
.vs/
```

`README.md`:
```markdown
# DrovaVoice (DrovaTTAI)

KI-Vertonung für *Drova: Forsaken Kin*. Ein MelonLoader-Mod spielt vorab erzeugte Sprachdateien ab; ein Python-Generator erzeugt sie lokal aus den Texten deiner Spielinstallation.

Dieses Repo enthält **keine** Spieltexte und **kein** Audio.

- Design: `docs/superpowers/specs/2026-10-10-drova-voice-design.md`
- Setup Spiel/Mod: `docs/setup.md`
- Generator: `cd generator && uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]"`
```

`generator/pyproject.toml`:
```toml
[project]
name = "drova-voice"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0", "num2words>=0.5.13"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
drova-voice = "drova_voice.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["drova_voice*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`generator/config.example.yaml`:
```yaml
# Kopieren nach generator/config.yaml und anpassen.
game_dir: "D:/Games/Steam/steamapps/common/Drova - Forsaken Kin"
language: de
```

`generator/drova_voice/__init__.py`:
```python
"""DrovaVoice generator."""
```

- [ ] **Step 2: venv anlegen**

Run: `cd generator && uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]"`
Expected: Installation von pyyaml, num2words, pytest ohne Fehler.

- [ ] **Step 3: Failing test schreiben** – `generator/tests/test_config.py`

```python
from pathlib import Path

import pytest

from drova_voice.config import load_config


def test_load_config_defaults(tmp_path):
    gen = tmp_path / "generator"
    gen.mkdir()
    cfg_file = gen / "config.yaml"
    cfg_file.write_text('game_dir: "C:/Game Dir"\n', encoding="utf-8")

    cfg = load_config(cfg_file)

    assert cfg.language == "de"
    assert cfg.repo_root == tmp_path.resolve()
    assert cfg.loc_dir == Path("C:/Game Dir/Drova_Data/StreamingAssets/Localization/de")
    assert cfg.data_dir == tmp_path.resolve() / "data"
    assert cfg.workers_dir == tmp_path.resolve() / "generator" / "workers"


def test_missing_game_dir_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("language: de\n", encoding="utf-8")
    with pytest.raises(ValueError, match="game_dir"):
        load_config(cfg_file)
```

- [ ] **Step 4: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'drova_voice.config'`)

- [ ] **Step 5: Implementieren** – `generator/drova_voice/config.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


@dataclass(frozen=True)
class Config:
    game_dir: Path
    language: str
    repo_root: Path

    @property
    def loc_dir(self) -> Path:
        return self.game_dir / "Drova_Data" / "StreamingAssets" / "Localization" / self.language

    @property
    def data_dir(self) -> Path:
        return self.repo_root / "data"

    @property
    def out_dir(self) -> Path:
        return self.repo_root / "out"

    @property
    def voices_dir(self) -> Path:
        return self.repo_root / "voices"

    @property
    def workers_dir(self) -> Path:
        return self.repo_root / "generator" / "workers"


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "game_dir" not in raw:
        raise ValueError(f"{path}: 'game_dir' fehlt")
    repo_root = Path(raw["repo_root"]) if raw.get("repo_root") else Path(path).resolve().parent.parent
    return Config(
        game_dir=Path(raw["game_dir"]),
        language=str(raw.get("language", "de")),
        repo_root=repo_root.resolve(),
    )
```

- [ ] **Step 6: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 7: Lokale Config anlegen (nicht committen)**

Run: `cp generator/config.example.yaml generator/config.yaml`

- [ ] **Step 8: Commit**

```bash
git add .gitignore README.md generator/pyproject.toml generator/config.example.yaml generator/drova_voice/__init__.py generator/drova_voice/config.py generator/tests/test_config.py
git commit -m "Add repo scaffolding and generator config" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Zeilen-IDs und gemeinsame Testvektoren (Python)

**Files:**
- Create: `tests/vectors/line_ids.json`, `generator/drova_voice/ids.py`
- Test: `generator/tests/test_ids.py`

**Interfaces:**
- Produces: `normalize_loca_path(path: str) -> str`, `statement_id(tree: str, loca_path: str, loca_key: str) -> str`, `choice_id(tree: str, loca_path: str, loca_key: str, choice_index: int) -> str`, `with_variant(line_id: str, variant: str | None) -> str`, `audio_filename(full_id: str) -> str` (alle in `drova_voice.ids`). Fehlerhafte Eingaben → `ValueError`.

- [ ] **Step 1: Vektor-Datei anlegen** – `tests/vectors/line_ids.json` (UTF-8 ohne BOM; Werte sind vorab berechnet und verbindlich)

```json
[
  {"kind": "statement", "tree": "DT_Main_NPC_Adela", "locaPath": "Dialog/NPC_Adela", "locaKey": "Plh_5", "choiceIndex": null, "variant": null,
   "expectedId": "DT_Main_NPC_Adela|Dialog/NPC_Adela|Plh_5", "expectedFile": "950774fdbc26dddf.ogg"},
  {"kind": "choice", "tree": "DT_Main_NPC_Adela", "locaPath": "Dialog\\NPC_Adela/", "locaKey": "Plh_19", "choiceIndex": 2, "variant": null,
   "expectedId": "DT_Main_NPC_Adela|Dialog/NPC_Adela|Plh_19|c2", "expectedFile": "7702474c8a24ee3e.ogg"},
  {"kind": "statement", "tree": "DT_WorldDialogue_Template", "locaPath": "/WorldDialogueCombat", "locaKey": "Plh_3", "choiceIndex": null, "variant": "f2",
   "expectedId": "DT_WorldDialogue_Template|WorldDialogueCombat|Plh_3#f2", "expectedFile": "f15de7a5cb1284dd.ogg"},
  {"kind": "statement", "tree": "DT_Bär", "locaPath": "Dialog/Ümlaut", "locaKey": "Plh_1", "choiceIndex": null, "variant": "neutral",
   "expectedId": "DT_Bär|Dialog/Ümlaut|Plh_1#neutral", "expectedFile": "98b91eed1e4804d3.ogg"}
]
```

- [ ] **Step 2: Failing test schreiben** – `generator/tests/test_ids.py`

```python
import json
from pathlib import Path

import pytest

from drova_voice.ids import audio_filename, choice_id, statement_id, with_variant

VECTORS = Path(__file__).resolve().parents[2] / "tests" / "vectors" / "line_ids.json"


def load_vectors():
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", load_vectors(), ids=lambda v: v["expectedId"])
def test_vectors(v):
    if v["kind"] == "choice":
        line_id = choice_id(v["tree"], v["locaPath"], v["locaKey"], v["choiceIndex"])
    else:
        line_id = statement_id(v["tree"], v["locaPath"], v["locaKey"])
    full_id = with_variant(line_id, v["variant"])
    assert full_id == v["expectedId"]
    assert audio_filename(full_id) == v["expectedFile"]


def test_rejects_separator_in_parts():
    with pytest.raises(ValueError):
        statement_id("DT|X", "Dialog/A", "Plh_1")


def test_rejects_negative_choice_index():
    with pytest.raises(ValueError):
        choice_id("DT_X", "Dialog/A", "Plh_1", -1)


def test_rejects_bad_variant():
    with pytest.raises(ValueError):
        with_variant("DT_X|Dialog/A|Plh_1", "a#b")


def test_empty_variant_is_noop():
    assert with_variant("DT_X|A|Plh_1", None) == "DT_X|A|Plh_1"
    assert with_variant("DT_X|A|Plh_1", "") == "DT_X|A|Plh_1"
```

- [ ] **Step 3: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_ids.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'drova_voice.ids'`)

- [ ] **Step 4: Implementieren** – `generator/drova_voice/ids.py`

```python
from __future__ import annotations

import hashlib

SEP = "|"
VARIANT_SEP = "#"


def normalize_loca_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _require_clean(value: str, name: str) -> None:
    if SEP in value or VARIANT_SEP in value:
        raise ValueError(f"{name} darf weder '{SEP}' noch '{VARIANT_SEP}' enthalten: {value!r}")


def statement_id(tree: str, loca_path: str, loca_key: str) -> str:
    path = normalize_loca_path(loca_path)
    for value, name in ((tree, "tree"), (path, "loca_path"), (loca_key, "loca_key")):
        _require_clean(value, name)
    return SEP.join((tree, path, loca_key))


def choice_id(tree: str, loca_path: str, loca_key: str, choice_index: int) -> str:
    if choice_index < 0:
        raise ValueError(f"choice_index muss >= 0 sein: {choice_index}")
    return f"{statement_id(tree, loca_path, loca_key)}{SEP}c{choice_index}"


def with_variant(line_id: str, variant: str | None) -> str:
    if not variant:
        return line_id
    _require_clean(variant, "variant")
    return f"{line_id}{VARIANT_SEP}{variant}"


def audio_filename(full_id: str) -> str:
    return hashlib.sha1(full_id.encode("utf-8")).hexdigest()[:16] + ".ogg"
```

- [ ] **Step 5: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_ids.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add tests/vectors/line_ids.json generator/drova_voice/ids.py generator/tests/test_ids.py
git commit -m "Add line id scheme with shared test vectors" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: DrovaVoice.Core – Zeilen-IDs in C#

**Files:**
- Create: `mod/Directory.Build.props`, `mod/DrovaVoice.sln`, `mod/DrovaVoice.Core/DrovaVoice.Core.csproj`, `mod/DrovaVoice.Core/LineIds.cs`, `mod/DrovaVoice.Core.Tests/DrovaVoice.Core.Tests.csproj`, `mod/DrovaVoice.Core.Tests/LineIdsTests.cs`

**Interfaces:**
- Consumes: `tests/vectors/line_ids.json` (Task 2)
- Produces: `DrovaVoice.Core.LineIds` mit `NormalizeLocaPath(string)`, `Statement(string tree, string locaPath, string locaKey)`, `Choice(string tree, string locaPath, string locaKey, int choiceIndex)`, `WithVariant(string lineId, string? variant)`, `AudioFileName(string fullId)`; ungültige Teile → `ArgumentException`, negativer Index → `ArgumentOutOfRangeException`. MSBuild-Property `$(DrovaGameDir)`.

- [ ] **Step 1: Build-Props und Projekte anlegen**

`mod/Directory.Build.props`:
```xml
<Project>
  <PropertyGroup>
    <DrovaGameDir Condition="'$(DrovaGameDir)' == '' and '$(DROVA_GAME_DIR)' != ''">$(DROVA_GAME_DIR)</DrovaGameDir>
    <DrovaGameDir Condition="'$(DrovaGameDir)' == ''">D:\Games\Steam\steamapps\common\Drova - Forsaken Kin</DrovaGameDir>
  </PropertyGroup>
</Project>
```

`mod/DrovaVoice.Core/DrovaVoice.Core.csproj`:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <Nullable>enable</Nullable>
    <LangVersion>latest</LangVersion>
    <ImplicitUsings>disable</ImplicitUsings>
    <RootNamespace>DrovaVoice.Core</RootNamespace>
  </PropertyGroup>
</Project>
```

`mod/DrovaVoice.Core.Tests/DrovaVoice.Core.Tests.csproj`:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
    <ImplicitUsings>disable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.11.1" />
    <PackageReference Include="xunit" Version="2.9.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="..\DrovaVoice.Core\DrovaVoice.Core.csproj" />
  </ItemGroup>
  <ItemGroup>
    <None Include="..\..\tests\vectors\line_ids.json" Link="vectors\line_ids.json" CopyToOutputDirectory="PreserveNewest" />
  </ItemGroup>
</Project>
```

Solution: `cd mod && dotnet new sln -n DrovaVoice && dotnet sln add DrovaVoice.Core/DrovaVoice.Core.csproj DrovaVoice.Core.Tests/DrovaVoice.Core.Tests.csproj`

- [ ] **Step 2: Failing test schreiben** – `mod/DrovaVoice.Core.Tests/LineIdsTests.cs`

```csharp
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class LineIdsTests
    {
        public sealed record Vector(
            string kind, string tree, string locaPath, string locaKey,
            int? choiceIndex, string? variant, string expectedId, string expectedFile);

        public static IEnumerable<object[]> Vectors()
        {
            string path = Path.Combine(AppContext.BaseDirectory, "vectors", "line_ids.json");
            var vectors = JsonSerializer.Deserialize<List<Vector>>(File.ReadAllText(path))!;
            foreach (var v in vectors) yield return new object[] { v };
        }

        [Theory]
        [MemberData(nameof(Vectors))]
        public void BuildsExpectedIdAndFileName(Vector v)
        {
            string id = v.kind == "choice"
                ? LineIds.Choice(v.tree, v.locaPath, v.locaKey, v.choiceIndex!.Value)
                : LineIds.Statement(v.tree, v.locaPath, v.locaKey);
            id = LineIds.WithVariant(id, v.variant);

            Assert.Equal(v.expectedId, id);
            Assert.Equal(v.expectedFile, LineIds.AudioFileName(id));
        }

        [Fact]
        public void RejectsSeparatorInParts() =>
            Assert.Throws<ArgumentException>(() => LineIds.Statement("DT|X", "Dialog/A", "Plh_1"));

        [Fact]
        public void RejectsNegativeChoiceIndex() =>
            Assert.Throws<ArgumentOutOfRangeException>(() => LineIds.Choice("DT_X", "Dialog/A", "Plh_1", -1));

        [Fact]
        public void EmptyVariantIsNoop() =>
            Assert.Equal("DT_X|A|Plh_1", LineIds.WithVariant("DT_X|A|Plh_1", ""));
    }
}
```

Zusätzlich leere Datei `mod/DrovaVoice.Core/LineIds.cs` mit nur `namespace DrovaVoice.Core { }`, damit das Projekt baut.

- [ ] **Step 3: Test laufen lassen, muss fehlschlagen**

Run: `dotnet test mod/DrovaVoice.Core.Tests`
Expected: Build-Fehler `The name 'LineIds' does not exist in the current context`

- [ ] **Step 4: Implementieren** – `mod/DrovaVoice.Core/LineIds.cs`

```csharp
using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Zeilen-IDs und Audio-Dateinamen. Muss exakt drova_voice/ids.py entsprechen
    /// (geprüft über tests/vectors/line_ids.json).
    /// </summary>
    public static class LineIds
    {
        public const char Separator = '|';
        public const char VariantSeparator = '#';

        public static string NormalizeLocaPath(string path) => path.Replace('\\', '/').Trim('/');

        public static string Statement(string tree, string locaPath, string locaKey)
        {
            string path = NormalizeLocaPath(locaPath);
            RequireClean(tree, nameof(tree));
            RequireClean(path, nameof(locaPath));
            RequireClean(locaKey, nameof(locaKey));
            return string.Join(Separator, tree, path, locaKey);
        }

        public static string Choice(string tree, string locaPath, string locaKey, int choiceIndex)
        {
            if (choiceIndex < 0) throw new ArgumentOutOfRangeException(nameof(choiceIndex));
            return Statement(tree, locaPath, locaKey) + Separator + "c" + choiceIndex.ToString(CultureInfo.InvariantCulture);
        }

        public static string WithVariant(string lineId, string? variant)
        {
            if (string.IsNullOrEmpty(variant)) return lineId;
            RequireClean(variant, nameof(variant));
            return lineId + VariantSeparator + variant;
        }

        public static string AudioFileName(string fullId)
        {
            using var sha1 = SHA1.Create();
            byte[] hash = sha1.ComputeHash(Encoding.UTF8.GetBytes(fullId));
            var sb = new StringBuilder(16 + 4);
            for (int i = 0; i < 8; i++) sb.Append(hash[i].ToString("x2", CultureInfo.InvariantCulture));
            return sb.Append(".ogg").ToString();
        }

        private static void RequireClean(string value, string name)
        {
            if (value.IndexOf(Separator) >= 0 || value.IndexOf(VariantSeparator) >= 0)
                throw new ArgumentException($"'{name}' darf weder '{Separator}' noch '{VariantSeparator}' enthalten: {value}", name);
        }
    }
}
```

- [ ] **Step 5: Tests laufen lassen**

Run: `dotnet test mod/DrovaVoice.Core.Tests`
Expected: `Passed!` (mindestens 4 Tests, die Theory-Fälle können als einer zählen)

- [ ] **Step 6: Commit**

```bash
git add mod/Directory.Build.props mod/DrovaVoice.sln mod/DrovaVoice.Core mod/DrovaVoice.Core.Tests
git commit -m "Add DrovaVoice.Core line ids matching Python vectors" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `.loc`-Parser

**Files:**
- Create: `generator/drova_voice/loc.py`
- Test: `generator/tests/test_loc.py`

**Interfaces:**
- Produces: `LocEntry` (frozen: `key: str`, `text: str`, `line: int` – 1-basierte Startzeile), `LocParseResult` (frozen: `entries: tuple[LocEntry, ...]`, `errors: tuple[int, ...]` – Zeilennummern nicht lesbarer Zeilen), `parse_loc(content: str) -> LocParseResult`, `read_loc_file(path: Path) -> LocParseResult`, `loc_rel_path(lang_dir: Path, file: Path, language: str) -> str` (z. B. `Dialog/NPC_Adela`).

- [ ] **Step 1: Failing test schreiben** – `generator/tests/test_loc.py`

```python
from pathlib import Path

from drova_voice.loc import loc_rel_path, parse_loc, read_loc_file


def test_single_line_entries_with_blank_lines():
    res = parse_loc("Tst_5 { Erster Satz Alpha! Zweiter Satz Alpha. }\n\nTst_7 { Beta Gamma. }\n")
    assert [(e.key, e.text, e.line) for e in res.entries] == [
        ("Tst_5", "Erster Satz Alpha! Zweiter Satz Alpha.", 1),
        ("Tst_7", "Beta Gamma.", 3),
    ]
    assert res.errors == ()


def test_crlf_and_bom(tmp_path):
    f = tmp_path / "NPC_X_de.loc"
    f.write_bytes("\ufeffPlh_1 { Grüß dich. }\r\n\r\nPlh_2 { Na? }\r\n".encode("utf-8"))
    res = read_loc_file(f)
    assert [(e.key, e.text) for e in res.entries] == [("Plh_1", "Grüß dich."), ("Plh_2", "Na?")]


def test_key_with_spaces_and_braces_in_text():
    res = parse_loc("Test Item_name { Testgegenstand {selten} }\n")
    assert res.entries[0].key == "Test Item_name"
    assert res.entries[0].text == "Testgegenstand {selten}"


def test_multiline_entry():
    content = "Letter_1 { Liebe Mara,\nich komme bald.\nDein Jero }\n\nPlh_2 { Ok. }\n"
    res = parse_loc(content)
    assert res.entries[0].key == "Letter_1"
    assert res.entries[0].text == "Liebe Mara,\nich komme bald.\nDein Jero"
    assert res.entries[1].key == "Plh_2"
    assert res.entries[1].line == 5


def test_empty_text():
    res = parse_loc("Plh_9 {  }\nPlh_10 {}\n")
    assert [(e.key, e.text) for e in res.entries] == [("Plh_9", ""), ("Plh_10", "")]


def test_garbage_line_is_reported_not_fatal():
    res = parse_loc("das ist kein Eintrag\nPlh_1 { Ja. }\n")
    assert res.errors == (1,)
    assert res.entries[0].key == "Plh_1"


def test_unterminated_multiline_is_reported():
    res = parse_loc("Plh_1 { Anfang\nohne Ende\n")
    assert res.entries == ()
    assert res.errors == (1,)


def test_loc_rel_path(tmp_path):
    lang_dir = tmp_path / "de"
    f = lang_dir / "Dialog" / "NPC_Adela_de.loc"
    assert loc_rel_path(lang_dir, f, "de") == "Dialog/NPC_Adela"
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_loc.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren** – `generator/drova_voice/loc.py`

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_START_RE = re.compile(r"^(.+?)\s*\{\s?(.*)$")


@dataclass(frozen=True)
class LocEntry:
    key: str
    text: str
    line: int


@dataclass(frozen=True)
class LocParseResult:
    entries: tuple[LocEntry, ...]
    errors: tuple[int, ...]


def parse_loc(content: str) -> LocParseResult:
    entries: list[LocEntry] = []
    errors: list[int] = []
    lines = content.lstrip("\ufeff").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = _START_RE.match(line)
        if not m:
            errors.append(i + 1)
            i += 1
            continue
        key, rest = m.group(1).strip(), m.group(2)
        start = i + 1
        if rest.rstrip().endswith("}"):
            entries.append(LocEntry(key, rest.rstrip()[:-1].strip(), start))
            i += 1
            continue
        buffer = [rest]
        j = i + 1
        while j < len(lines) and not lines[j].rstrip().endswith("}"):
            buffer.append(lines[j])
            j += 1
        if j >= len(lines):
            errors.append(start)
            break
        buffer.append(lines[j].rstrip()[:-1])
        entries.append(LocEntry(key, "\n".join(buffer).strip(), start))
        i = j + 1
    return LocParseResult(tuple(entries), tuple(errors))


def read_loc_file(path: Path) -> LocParseResult:
    return parse_loc(Path(path).read_text(encoding="utf-8-sig"))


def loc_rel_path(lang_dir: Path, file: Path, language: str) -> str:
    rel = Path(file).relative_to(lang_dir).as_posix()
    suffix = f"_{language}.loc"
    if rel.endswith(suffix):
        return rel[: -len(suffix)]
    return rel[: -len(".loc")] if rel.endswith(".loc") else rel
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_loc.py -v`
Expected: 8 passed

- [ ] **Step 5: Gegen echte Spieldateien prüfen (Smoke, kein Test)**

Run:
```bash
cd generator && .venv/Scripts/python -c "
from pathlib import Path
from drova_voice.config import load_config
from drova_voice.loc import read_loc_file
cfg = load_config(Path('config.yaml'))
n = e = 0
for f in sorted(cfg.loc_dir.rglob('*.loc')):
    r = read_loc_file(f); n += len(r.entries); e += len(r.errors)
    if r.errors: print(f.relative_to(cfg.loc_dir), r.errors[:5])
print('Einträge', n, 'Fehlerzeilen', e)
"
```
Expected: ca. 22.500 Einträge; Fehlerzeilen nahe 0. Jede gemeldete Fehlerzeile ansehen – wenn es ein reales Format ist, das der Parser nicht kann: Test dafür ergänzen, Parser anpassen, erneut laufen lassen.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/loc.py generator/tests/test_loc.py
git commit -m "Add .loc parser" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Sprechtext (Regieanweisungen, Tags, GVAR, Zahlen, Lexikon)

**Files:**
- Create: `generator/drova_voice/speech_text.py`
- Test: `generator/tests/test_speech_text.py`

**Interfaces:**
- Produces: `STAGE_RE`, `GVAR_RE` (compiled regex), `StageDirection` (frozen: `text: str`, `pos: int` – Zeichenindex im fertigen Sprechtext), `SpeechText` (frozen: `text: str`, `stage: tuple[StageDirection, ...]`, `unresolved_gvars: tuple[str, ...]`, Property `is_speakable: bool`), `substitute_gvars(text: str, values: Mapping[str, str]) -> tuple[str, tuple[str, ...]]`, `apply_lexicon(text: str, lexicon: Mapping[str, str]) -> str`, `extract_stage_directions(text: str) -> tuple[str, tuple[StageDirection, ...]]`, `build_speech_text(raw: str, gvar_values: Mapping[str, str] | None = None, lexicon: Mapping[str, str] | None = None) -> SpeechText`.
- GVAR-Schlüssel sind `"<Set>.<Var>"`, z. B. `"QuestVars_Beispiel_Config.Betrag"`. Nicht aufgelöste Platzhalter werden aus dem Text entfernt und in `unresolved_gvars` gemeldet (der Aufrufer entscheidet, ob die Zeile übersprungen wird). Den Spielernamen ersetzt der Aufrufer **vorher** (Task 6).

- [ ] **Step 1: Failing test schreiben** – `generator/tests/test_speech_text.py`

```python
from drova_voice.speech_text import StageDirection, apply_lexicon, build_speech_text


def test_line_with_stage_direction_and_config_gvar():
    raw = ("*blinzelt langsam* Die Brücke aus Holz trägt noch gut. "
           "Der $GVAR:QuestVars_Beispiel_Config.Betrag$ Betrag passt mir gut.")
    st = build_speech_text(raw, {"QuestVars_Beispiel_Config.Betrag": "150"})
    assert st.text == "Die Brücke aus Holz trägt noch gut. Der einhundertfünfzig Betrag passt mir gut."
    assert st.stage == (StageDirection("blinzelt langsam", 0),)
    assert st.unresolved_gvars == ()


def test_stage_direction_in_the_middle_keeps_punctuation_clean():
    st = build_speech_text("Na gut *seufzt*, dann eben.")
    assert st.text == "Na gut, dann eben."
    assert st.stage == (StageDirection("seufzt", 6),)


def test_unresolved_gvar_is_removed_and_reported():
    st = build_speech_text("Du hast $GVAR:EVars_Beispiel.SilberMenge$ Silber.")
    assert st.text == "Du hast Silber."
    assert st.unresolved_gvars == ("EVars_Beispiel.SilberMenge",)


def test_br_becomes_sentence_break_or_space():
    assert build_speech_text("Hallo<br>Wie geht's?").text == "Hallo. Wie geht's?"
    assert build_speech_text("Hallo!<br><br>Wie?").text == "Hallo! Wie?"


def test_rich_text_tags_are_removed():
    assert build_speech_text("Nimm den <color=#ff0000>Schlüssel</color>.").text == "Nimm den Schlüssel."


def test_only_stage_direction_is_not_speakable():
    st = build_speech_text("*grinst*")
    assert st.text == ""
    assert not st.is_speakable


def test_ellipsis_only_is_not_speakable():
    assert not build_speech_text("...").is_speakable


def test_numbers_to_german_words():
    assert build_speech_text("Das kostet 25 Münzen.").text == "Das kostet fünfundzwanzig Münzen."


def test_lexicon_whole_words_only():
    assert apply_lexicon("Nemeton und Nemetonia", {"Nemeton": "Nemmeton"}) == "Nemmeton und Nemetonia"
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_speech_text.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren** – `generator/drova_voice/speech_text.py`

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from num2words import num2words

STAGE_RE = re.compile(r"\*([^*\n]{1,80})\*")
GVAR_RE = re.compile(r"\$GVAR:([^$]+)\$")
_BR_RE = re.compile(r"\s*<br\s*/?>\s*", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_NUM_RE = re.compile(r"\b\d+\b")
_WS_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.!?…;:])")


@dataclass(frozen=True)
class StageDirection:
    text: str
    pos: int


@dataclass(frozen=True)
class SpeechText:
    text: str
    stage: tuple[StageDirection, ...] = ()
    unresolved_gvars: tuple[str, ...] = ()

    @property
    def is_speakable(self) -> bool:
        return any(ch.isalnum() for ch in self.text)


def substitute_gvars(text: str, values: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    unresolved: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in values:
            return str(values[name])
        unresolved.append(name)
        return ""

    return GVAR_RE.sub(repl, text), tuple(unresolved)


def _replace_br(text: str) -> str:
    def repl(m: re.Match) -> str:
        before = text[: m.start()].rstrip()
        return ". " if before and before[-1].isalnum() else " "

    return _BR_RE.sub(repl, text)


def _numbers_to_words(text: str) -> str:
    return _NUM_RE.sub(lambda m: num2words(int(m.group(0)), lang="de"), text)


def apply_lexicon(text: str, lexicon: Mapping[str, str]) -> str:
    for word, spoken in lexicon.items():
        text = re.sub(rf"\b{re.escape(word)}\b", spoken, text)
    return text


def _tidy(text: str) -> str:
    text = _WS_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return text.strip()


def extract_stage_directions(text: str) -> tuple[str, tuple[StageDirection, ...]]:
    parts: list[str] = []
    found: list[StageDirection] = []
    last = 0
    for m in STAGE_RE.finditer(text):
        parts.append(text[last : m.start()])
        last = m.end()
        found.append(StageDirection(m.group(1).strip(), len(_tidy("".join(parts)))))
    parts.append(text[last:])
    clean = _tidy("".join(parts))
    return clean, tuple(StageDirection(s.text, min(s.pos, len(clean))) for s in found)


def build_speech_text(
    raw: str,
    gvar_values: Mapping[str, str] | None = None,
    lexicon: Mapping[str, str] | None = None,
) -> SpeechText:
    text, unresolved = substitute_gvars(raw, gvar_values or {})
    text = _replace_br(text)
    text = _TAG_RE.sub("", text)
    text = _numbers_to_words(text)
    if lexicon:
        text = apply_lexicon(text, lexicon)
    clean, stage = extract_stage_directions(text)
    return SpeechText(clean, stage, unresolved)
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_speech_text.py -v`
Expected: 9 passed. Falls `num2words` eine andere Schreibweise liefert (z. B. „hundertfünfzig“), den tatsächlichen Wert mit `python -c "from num2words import num2words; print(num2words(150, lang='de'))"` prüfen und **die Testerwartung** daran anpassen (num2words ist die Referenz, kein Bug).

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/speech_text.py generator/tests/test_speech_text.py
git commit -m "Add speech text normalization" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Spielernamen-Varianten

**Files:**
- Create: `generator/drova_voice/player_name.py`
- Test: `generator/tests/test_player_name.py`

**Interfaces:**
- Produces: `NAME_TOKEN = "$GVAR:EVars_Player.Name$"`, `DEFAULT_NAME = "Arden"`, `NameVariants` (frozen: `arden: str`, `neutral: str | None`, Property `needs_review: bool` = `neutral is None`), `has_player_name(text: str) -> bool`, `make_name_variants(text: str) -> NameVariants`. `neutral` ist `None`, wenn keine Regel greift – diese Zeilen bekommen später einen LLM-Vorschlag.

- [ ] **Step 1: Failing test schreiben** – `generator/tests/test_player_name.py`

```python
import pytest

from drova_voice.player_name import NAME_TOKEN, has_player_name, make_name_variants

N = NAME_TOKEN


@pytest.mark.parametrize("raw, neutral", [
    (f"Danke, {N}. Der Vogt Zerinda wartet am Brunnen.", "Danke. Der Vogt Zerinda wartet am Brunnen."),
    (f"Hallo {N}! Der Wald riecht nach Regen.", "Hallo! Der Wald riecht nach Regen."),
    (f"Hallo {N}, der Wald riecht nach Regen.", "Hallo, der Wald riecht nach Regen."),
    (f"Nun zu dir, {N} ... Pass auf die Brücke auf.", "Nun zu dir ... Pass auf die Brücke auf."),
    (f"Lanzo! {N}!", "Lanzo!"),
    (f"{N}, komm mal her.", "Komm mal her."),
])
def test_vocative_is_removed(raw, neutral):
    v = make_name_variants(raw)
    assert v.neutral == neutral
    assert not v.needs_review


@pytest.mark.parametrize("raw", [
    f"Ich bin {N}.",
    f"Vorsicht, Pamph. {N} schafft das bestimmt.",
    f"Nett, dass du kommst {N} ... Der Tee ist noch warm.",
    f"{N}!",
])
def test_name_inside_sentence_needs_review(raw):
    v = make_name_variants(raw)
    assert v.neutral is None
    assert v.needs_review


def test_arden_variant():
    assert make_name_variants(f"Ich bin {N}.").arden == "Ich bin Arden."


def test_has_player_name():
    assert has_player_name(f"Hallo {N}!")
    assert not has_player_name("Hallo!")
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_player_name.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren** – `generator/drova_voice/player_name.py`

```python
from __future__ import annotations

import re
from dataclasses import dataclass

NAME_TOKEN = "$GVAR:EVars_Player.Name$"
DEFAULT_NAME = "Arden"

GREETINGS = ("Hallo", "Hey", "Hi", "Na", "Ah", "Oh", "Danke", "Willkommen", "Moin", "Tag", "Servus", "Grüß dich")

_N = re.escape(NAME_TOKEN)
_RULES: list[tuple[re.Pattern, object]] = [
    # "Danke, NAME." / "Wir gehen zum Wald, NAME ..."
    (re.compile(rf",\s*{_N}(?=\s*(?:\.\.\.|…|[.!?]|$))"), ""),
    # "NAME, komm her." am Satzanfang
    (re.compile(rf"(?:^|(?<=[.!?…]\s)){_N}\s*,\s*(\w)"), lambda m: m.group(1).upper()),
    # "Lanzo! NAME!" – Name als eigener Ausruf nach Satzende
    (re.compile(rf"(?<=[.!?…]\s){_N}\s*[.!?]\s*"), ""),
    # "Hallo NAME!" / "Hallo NAME, ..."
    (re.compile(rf"\b({'|'.join(map(re.escape, GREETINGS))})\s+{_N}(?=\s*[,.!?…])"), r"\1"),
]


@dataclass(frozen=True)
class NameVariants:
    arden: str
    neutral: str | None

    @property
    def needs_review(self) -> bool:
        return self.neutral is None


def has_player_name(text: str) -> bool:
    return NAME_TOKEN in text


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.!?](?!\.))", r"\1", text)
    return text.strip()


def _neutralize(text: str) -> str | None:
    result = text
    for pattern, repl in _RULES:
        result = pattern.sub(repl, result)
    if NAME_TOKEN in result:
        return None
    result = _tidy(result)
    if not any(ch.isalnum() for ch in result):
        return None
    return result


def make_name_variants(text: str) -> NameVariants:
    return NameVariants(arden=text.replace(NAME_TOKEN, DEFAULT_NAME), neutral=_neutralize(text))
```

Hinweis zur Regel 3: Der Test `f"{N}!"` (Name als ganze Zeile) muss `None` liefern – deshalb greift Regel 3 nur **nach** einem Satzende (`(?<=[.!?…]\s)`), nicht am Zeilenanfang.

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_player_name.py -v`
Expected: 12 passed

- [ ] **Step 5: Gegen echte Zeilen messen (Smoke)**

Run:
```bash
cd generator && .venv/Scripts/python -c "
from pathlib import Path
from drova_voice.config import load_config
from drova_voice.loc import read_loc_file
from drova_voice.player_name import has_player_name, make_name_variants
cfg = load_config(Path('config.yaml'))
auto = review = 0
for f in sorted(cfg.loc_dir.rglob('*.loc')):
    for e in read_loc_file(f).entries:
        if has_player_name(e.text):
            if make_name_variants(e.text).needs_review: review += 1
            else: auto += 1
print('automatisch', auto, 'Prüfung nötig', review)
"
```
Expected: ca. 150 automatisch, ca. 80–110 mit Prüfbedarf. 10 zufällige automatische Ergebnisse ansehen; ist eines grammatisch falsch, Testfall ergänzen und Regel korrigieren.

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/player_name.py generator/tests/test_player_name.py
git commit -m "Add player name variants" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Emotionsmodell und Regieanweisungs-Mapping

**Files:**
- Create: `generator/drova_voice/emotions.py`
- Test: `generator/tests/test_emotions.py`

**Interfaces:**
- Consumes: `StageDirection` aus `drova_voice.speech_text`
- Produces: `EMOTIONS: tuple[str, ...]`, `EVENTS: tuple[str, ...]`, `SOURCES = ("default", "stage", "llm", "manual")`, `Event` (frozen: `tag: str`, `pos: int`), `EmotionTag` (dataclass: `emotion: str = "neutral"`, `intensity: float = 0.0`, `events: list[Event]`, `emphasis: list[str]`, `notes: list[str]`, `source: str = "default"`; validiert in `__post_init__` → `ValueError`; `to_dict() -> dict`, `EmotionTag.from_dict(d: dict) -> EmotionTag`), `from_stage_directions(stage: Sequence[StageDirection]) -> EmotionTag`.

- [ ] **Step 1: Failing test schreiben** – `generator/tests/test_emotions.py`

```python
import pytest

from drova_voice.emotions import EmotionTag, Event, from_stage_directions
from drova_voice.speech_text import StageDirection


def test_defaults_are_neutral():
    t = EmotionTag()
    assert (t.emotion, t.intensity, t.events, t.source) == ("neutral", 0.0, [], "default")


@pytest.mark.parametrize("kwargs", [
    {"emotion": "furious"},
    {"intensity": 1.5},
    {"events": [Event("cough", 0)]},
    {"source": "guess"},
])
def test_validation(kwargs):
    with pytest.raises(ValueError):
        EmotionTag(**kwargs)


def test_roundtrip_dict():
    t = EmotionTag("stern", 0.6, [Event("sigh", 3)], ["nie"], ["whisper"], "llm")
    assert EmotionTag.from_dict(t.to_dict()) == t


def test_sigh_becomes_event():
    t = from_stage_directions([StageDirection("seufzt", 0)])
    assert t.events == [Event("sigh", 0)]
    assert t.emotion == "neutral"
    assert t.source == "stage"


def test_strongest_emotion_wins_and_events_collect():
    t = from_stage_directions([StageDirection("grinst", 0), StageDirection("knurrt leise", 5)])
    assert (t.emotion, t.intensity) == ("angry", 0.5)
    assert t.events == [Event("growl", 5)]


def test_notes_for_whisper_and_drunk():
    t = from_stage_directions([StageDirection("flüstert", 0), StageDirection("hick", 4)])
    assert t.notes == ["whisper", "drunk"]


def test_word_start_matching_avoids_false_hits():
    t = from_stage_directions([StageDirection("schickt dich weg", 0)])
    assert t.notes == []
    assert t.source == "default"


def test_unknown_direction_keeps_default():
    t = from_stage_directions([StageDirection("tanzt", 0)])
    assert t == EmotionTag()
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_emotions.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren** – `generator/drova_voice/emotions.py`

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from drova_voice.speech_text import StageDirection

EMOTIONS = ("neutral", "angry", "contemplative", "excited", "joyful", "mundane",
            "nervous", "sad", "stern", "surprised", "tender")
EVENTS = ("gasp", "giggle", "growl", "gulp", "laugh", "pause", "scoff", "sigh", "sob", "um")
SOURCES = ("default", "stage", "llm", "manual")


@dataclass(frozen=True)
class Event:
    tag: str
    pos: int


@dataclass
class EmotionTag:
    emotion: str = "neutral"
    intensity: float = 0.0
    events: list[Event] = field(default_factory=list)
    emphasis: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = "default"

    def __post_init__(self) -> None:
        if self.emotion not in EMOTIONS:
            raise ValueError(f"Unbekannte Emotion: {self.emotion}")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError(f"Intensität außerhalb 0..1: {self.intensity}")
        for ev in self.events:
            if ev.tag not in EVENTS:
                raise ValueError(f"Unbekannter Laut: {ev.tag}")
        if self.source not in SOURCES:
            raise ValueError(f"Unbekannte Quelle: {self.source}")

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "intensity": self.intensity,
            "events": [{"tag": e.tag, "pos": e.pos} for e in self.events],
            "emphasis": list(self.emphasis),
            "notes": list(self.notes),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionTag":
        return cls(
            emotion=d.get("emotion", "neutral"),
            intensity=float(d.get("intensity", 0.0)),
            events=[Event(e["tag"], int(e["pos"])) for e in d.get("events", [])],
            emphasis=list(d.get("emphasis", [])),
            notes=list(d.get("notes", [])),
            source=d.get("source", "default"),
        )


@dataclass(frozen=True)
class _Effect:
    emotion: str | None = None
    intensity: float = 0.0
    event: str | None = None
    note: str | None = None


# Reihenfolge: spezifische Wendungen vor einzelnen Verben.
_STAGE_RULES: list[tuple[str, _Effect]] = [
    ("knirscht mit den zähnen", _Effect("angry", 0.6)),
    ("runzelt die stirn", _Effect("stern", 0.3)),
    ("mustert", _Effect("contemplative", 0.3)),
    ("seufzt", _Effect(event="sigh")),
    ("stöhnt", _Effect(event="sigh")),
    ("schluchzt", _Effect("sad", 0.7, "sob")),
    ("weint", _Effect("sad", 0.8, "sob")),
    ("kichert", _Effect("joyful", 0.4, "giggle")),
    ("lacht", _Effect("joyful", 0.5, "laugh")),
    ("grinst", _Effect("joyful", 0.3)),
    ("lächelt", _Effect("tender", 0.3)),
    ("zwinkert", _Effect("joyful", 0.3)),
    ("knurrt", _Effect("angry", 0.5, "growl")),
    ("schnaubt", _Effect("stern", 0.4, "scoff")),
    ("grummelt", _Effect("stern", 0.4)),
    ("schluckt", _Effect("nervous", 0.4, "gulp")),
    ("keucht", _Effect(event="gasp")),
    ("räuspert", _Effect(event="um")),
    ("flüstert", _Effect(note="whisper")),
    ("hick", _Effect(note="drunk")),
    ("brüllt", _Effect("angry", 0.8)),
    ("schreit", _Effect("angry", 0.8)),
]
_COMPILED = [(re.compile(rf"\b{re.escape(needle)}"), eff) for needle, eff in _STAGE_RULES]


def from_stage_directions(stage: Sequence[StageDirection]) -> EmotionTag:
    tag = EmotionTag()
    matched = False
    for sd in stage:
        low = sd.text.lower()
        for pattern, eff in _COMPILED:
            if not pattern.search(low):
                continue
            matched = True
            if eff.emotion and eff.intensity > tag.intensity:
                tag.emotion, tag.intensity = eff.emotion, eff.intensity
            if eff.event:
                tag.events.append(Event(eff.event, sd.pos))
            if eff.note and eff.note not in tag.notes:
                tag.notes.append(eff.note)
            break
    if matched:
        tag.source = "stage"
    return tag
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_emotions.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/emotions.py generator/tests/test_emotions.py
git commit -m "Add engine-neutral emotion model and stage direction mapping" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Engine-spezifisches Rendering

**Files:**
- Create: `generator/drova_voice/render.py`
- Test: `generator/tests/test_render.py`

**Interfaces:**
- Consumes: `EmotionTag`, `Event` (Task 7)
- Produces: `KITTEN_MIN_INTENSITY = 0.3`, `render_kitten(text: str, tag: EmotionTag) -> str`, `chatterbox_params(tag: EmotionTag) -> dict[str, float]` (Schlüssel `exaggeration`, `cfg_weight`), `render_request(engine: str, text: str, tag: EmotionTag) -> tuple[str, dict]` für Engines `kitten`, `chatterbox`, `xtts`, `fake`; sonst `ValueError`.

- [ ] **Step 1: Failing test schreiben** – `generator/tests/test_render.py`

```python
import pytest

from drova_voice.emotions import EmotionTag, Event
from drova_voice.render import chatterbox_params, render_kitten, render_request


def test_kitten_emotion_prefix_and_event():
    tag = EmotionTag("stern", 0.3, [Event("sigh", 0)])
    assert render_kitten("Na gut, dann eben.", tag) == "[stern] <sigh> Na gut, dann eben."


def test_kitten_event_in_the_middle():
    tag = EmotionTag(events=[Event("laugh", 6)])
    assert render_kitten("Hallo! Du hier?", tag) == "Hallo! <laugh> Du hier?"


def test_kitten_low_intensity_has_no_prefix():
    assert render_kitten("Schön.", EmotionTag("joyful", 0.2)) == "Schön."


def test_kitten_neutral_plain():
    assert render_kitten("Hallo.", EmotionTag()) == "Hallo."


def test_kitten_emphasis_first_occurrence_whole_word():
    tag = EmotionTag(emphasis=["nie"])
    assert render_kitten("Das mache ich nie wieder, nie.", tag) == "Das mache ich (((nie))) wieder, nie."
    assert render_kitten("Niemand.", EmotionTag(emphasis=["nie"])) == "Niemand."


@pytest.mark.parametrize("tag, expected", [
    (EmotionTag(), {"exaggeration": 0.5, "cfg_weight": 0.5}),
    (EmotionTag("angry", 1.0), {"exaggeration": 0.9, "cfg_weight": 0.3}),
    (EmotionTag("sad", 0.5), {"exaggeration": 0.4, "cfg_weight": 0.5}),
])
def test_chatterbox_params(tag, expected):
    assert chatterbox_params(tag) == expected


def test_render_request_dispatch():
    tag = EmotionTag("angry", 1.0, [Event("growl", 0)])
    assert render_request("kitten", "Raus!", tag) == ("[angry] <growl> Raus!", {})
    assert render_request("chatterbox", "Raus!", tag) == ("Raus!", {"exaggeration": 0.9, "cfg_weight": 0.3})
    assert render_request("xtts", "Raus!", tag) == ("Raus!", {})
    assert render_request("fake", "Raus!", tag) == ("Raus!", {})
    with pytest.raises(ValueError):
        render_request("unknown", "Raus!", tag)
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren** – `generator/drova_voice/render.py`

```python
from __future__ import annotations

import re

from drova_voice.emotions import EmotionTag

KITTEN_MIN_INTENSITY = 0.3
_HIGH_AROUSAL = {"angry", "excited", "surprised", "joyful", "stern"}
_LOW_AROUSAL = {"sad", "tender", "contemplative", "mundane"}


def render_kitten(text: str, tag: EmotionTag) -> str:
    s = text
    for ev in sorted(tag.events, key=lambda e: e.pos, reverse=True):
        p = max(0, min(ev.pos, len(s)))
        s = f"{s[:p]} <{ev.tag}> {s[p:]}"
    s = re.sub(r"\s+", " ", s).strip()
    for word in tag.emphasis:
        s = re.sub(rf"(?<![\w(])({re.escape(word)})(?![\w)])", r"(((\1)))", s, count=1)
    if tag.emotion != "neutral" and tag.intensity >= KITTEN_MIN_INTENSITY:
        s = f"[{tag.emotion}] {s}"
    return s


def chatterbox_params(tag: EmotionTag) -> dict[str, float]:
    exaggeration = 0.5
    if tag.emotion in _HIGH_AROUSAL:
        exaggeration = 0.5 + 0.4 * tag.intensity
    elif tag.emotion in _LOW_AROUSAL:
        exaggeration = 0.5 - 0.2 * tag.intensity
    exaggeration = round(exaggeration, 3)
    return {"exaggeration": exaggeration, "cfg_weight": 0.3 if exaggeration > 0.7 else 0.5}


def render_request(engine: str, text: str, tag: EmotionTag) -> tuple[str, dict]:
    if engine == "kitten":
        return render_kitten(text, tag), {}
    if engine == "chatterbox":
        return text, chatterbox_params(tag)
    if engine in ("xtts", "fake"):
        return text, {}
    raise ValueError(f"Unbekannte Engine: {engine}")
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/render.py generator/tests/test_render.py
git commit -m "Add engine-specific emotion rendering" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Worker-Protokoll, Fake-Worker, EngineClient

**Files:**
- Create: `generator/drova_voice/engines/__init__.py` (leer), `generator/drova_voice/engines/protocol.py`, `generator/drova_voice/engines/client.py`, `generator/workers/_common/worker_loop.py`, `generator/workers/fake/worker.py`
- Test: `generator/tests/test_engine_client.py`

**Interfaces:**
- Produces:
  - `SynthRequest` (frozen: `id: str`, `text: str`, `out_path: str`, `voice: str | None = None`, `reference: str | None = None`, `params: dict = {}`; `to_json() -> str`)
  - `SynthResponse` (frozen: `id: str | None`, `ok: bool`, `out_path: str | None = None`, `sample_rate: int | None = None`, `duration: float | None = None`, `error: str | None = None`; `SynthResponse.from_dict(d: dict)`)
  - `EngineError(RuntimeError)`, `EngineClient(cmd: Sequence[str], cwd=None)` mit Attributen `engine`, `model`, Methoden `synth(req: SynthRequest) -> SynthResponse`, `close()`, Context-Manager
  - `worker_command(workers_dir: Path, engine: str) -> list[str]`
  - Worker-Seite: `serve(engine: str, model: str, load: Callable[[], Any], synth: Callable[[Any, dict], tuple[int, float]]) -> None` in `workers/_common/worker_loop.py`
- Protokoll: Worker schreibt zuerst `{"ready": true, "engine": ..., "model": ...}`, dann pro Anfragezeile genau eine Antwortzeile `{"id", "ok", "out_path", "sample_rate", "duration"}` oder `{"id", "ok": false, "error"}`. Alles andere, was Bibliotheken drucken, geht auf stderr.

- [ ] **Step 1: Worker-Loop und Fake-Worker anlegen**

`generator/workers/_common/worker_loop.py`:
```python
"""Gemeinsame Schleife für Engine-Worker (JSON-Lines über stdin/stdout).

Nur stdlib: wird von Workern in fremden venvs importiert.
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable


def serve(engine: str, model: str, load: Callable[[], Any], synth: Callable[[Any, dict], tuple[int, float]]) -> None:
    proto = sys.stdout
    sys.stdout = sys.stderr  # Ausgaben von Bibliotheken dürfen das Protokoll nicht stören
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(proto, "reconfigure"):
        proto.reconfigure(encoding="utf-8")

    def send(obj: dict) -> None:
        proto.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proto.flush()

    state = load()
    send({"ready": True, "engine": engine, "model": model})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            send({"id": None, "ok": False, "error": f"Ungültiges JSON: {e}"})
            continue
        try:
            sample_rate, duration = synth(state, req)
            send({"id": req.get("id"), "ok": True, "out_path": req["out_path"],
                  "sample_rate": sample_rate, "duration": duration})
        except Exception as e:  # noqa: BLE001 – jeder Fehler wird gemeldet, der Worker lebt weiter
            traceback.print_exc()
            send({"id": req.get("id"), "ok": False, "error": f"{type(e).__name__}: {e}"})
```

`generator/workers/fake/worker.py`:
```python
"""Fake-Engine für Tests: schreibt einen Sinuston, Länge abhängig von der Textlänge."""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

RATE = 22050


def load():
    print("fake: lade Modell ... (dieser Text muss auf stderr landen)")
    return None


def synth(_state, req: dict) -> tuple[int, float]:
    text = req["text"]
    if "FAIL" in text:
        raise RuntimeError("absichtlicher Fehler")
    print(f"fake: synth {text!r}")
    duration = max(0.2, 0.05 * len(text))
    frames = int(RATE * duration)
    with wave.open(req["out_path"], "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / RATE))) for i in range(frames)))
    return RATE, frames / RATE


if __name__ == "__main__":
    serve("fake", "sine-1", load, synth)
```

- [ ] **Step 2: Failing test schreiben** – `generator/tests/test_engine_client.py`

```python
import sys
import wave
from pathlib import Path

import pytest

from drova_voice.engines.client import EngineClient, EngineError, worker_command
from drova_voice.engines.protocol import SynthRequest

WORKERS = Path(__file__).resolve().parents[1] / "workers"
FAKE = [sys.executable, str(WORKERS / "fake" / "worker.py")]


def test_handshake_and_synth(tmp_path):
    out = tmp_path / "a.wav"
    with EngineClient(FAKE) as client:
        assert (client.engine, client.model) == ("fake", "sine-1")
        resp = client.synth(SynthRequest(id="1", text="Grüß dich, Wanderer.", out_path=str(out)))
    assert resp.ok and resp.id == "1"
    assert resp.duration == pytest.approx(1.0, abs=0.01)
    with wave.open(str(out)) as w:
        assert w.getframerate() == 22050


def test_failure_is_reported_and_worker_survives(tmp_path):
    with EngineClient(FAKE) as client:
        bad = client.synth(SynthRequest(id="x", text="FAIL", out_path=str(tmp_path / "x.wav")))
        good = client.synth(SynthRequest(id="y", text="Hallo", out_path=str(tmp_path / "y.wav")))
    assert not bad.ok and "absichtlicher Fehler" in bad.error
    assert good.ok


def test_dead_worker_raises():
    with pytest.raises(EngineError):
        EngineClient([sys.executable, "-c", "import sys; sys.exit(3)"])


def test_worker_command_for_stdlib_worker_uses_current_python():
    assert worker_command(WORKERS, "fake") == [sys.executable, str(WORKERS / "fake" / "worker.py")]


def test_worker_command_unknown_engine():
    with pytest.raises(EngineError, match="Unbekannte Engine"):
        worker_command(WORKERS, "nope")


def test_worker_command_missing_venv(tmp_path):
    wdir = tmp_path / "heavy"
    wdir.mkdir()
    (wdir / "worker.py").write_text("")
    (wdir / "requirements.txt").write_text("torch\n")
    with pytest.raises(EngineError, match="venv"):
        worker_command(tmp_path, "heavy")
```

- [ ] **Step 3: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_engine_client.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'drova_voice.engines'`)

- [ ] **Step 4: Implementieren**

`generator/drova_voice/engines/protocol.py`:
```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields


@dataclass(frozen=True)
class SynthRequest:
    id: str
    text: str
    out_path: str
    voice: str | None = None
    reference: str | None = None
    params: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass(frozen=True)
class SynthResponse:
    id: str | None
    ok: bool
    out_path: str | None = None
    sample_rate: int | None = None
    duration: float | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "SynthResponse":
        return cls(**{f.name: d.get(f.name) for f in fields(cls)})
```

`generator/drova_voice/engines/client.py`:
```python
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from drova_voice.engines.protocol import SynthRequest, SynthResponse

_MAX_NOISE_LINES = 1000


class EngineError(RuntimeError):
    pass


class EngineClient:
    def __init__(self, cmd: Sequence[str], cwd: str | Path | None = None):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        self._proc = subprocess.Popen(
            list(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=cwd, env=env,
            text=True, encoding="utf-8", bufsize=1,
        )
        hello = self._read()
        if not hello.get("ready"):
            self.close()
            raise EngineError(f"Worker nicht bereit: {hello}")
        self.engine = hello.get("engine")
        self.model = hello.get("model")

    def _read(self) -> dict:
        for _ in range(_MAX_NOISE_LINES):
            line = self._proc.stdout.readline()
            if not line:
                raise EngineError(f"Worker beendet (Exit-Code {self._proc.poll()})")
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
            print(f"[worker stdout] {line}", file=sys.stderr)
        raise EngineError("Worker liefert kein gültiges Protokoll")

    def synth(self, req: SynthRequest) -> SynthResponse:
        self._proc.stdin.write(req.to_json() + "\n")
        self._proc.stdin.flush()
        resp = SynthResponse.from_dict(self._read())
        if resp.id != req.id:
            raise EngineError(f"Antwort-ID {resp.id!r} passt nicht zu Anfrage {req.id!r}")
        return resp

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self._proc.kill()

    def __enter__(self) -> "EngineClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def worker_command(workers_dir: Path, engine: str) -> list[str]:
    wdir = Path(workers_dir) / engine
    script = wdir / "worker.py"
    if not script.exists():
        raise EngineError(f"Unbekannte Engine '{engine}': {script} fehlt")
    py = wdir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if py.exists():
        return [str(py), str(script)]
    if (wdir / "requirements.txt").exists():
        raise EngineError(f"venv für '{engine}' fehlt: {py}. Siehe {wdir / 'README.md'}")
    return [sys.executable, str(script)]
```

`generator/drova_voice/engines/__init__.py`: leere Datei.

- [ ] **Step 5: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_engine_client.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add generator/drova_voice/engines generator/workers/_common generator/workers/fake generator/tests/test_engine_client.py
git commit -m "Add engine worker protocol, client and fake worker" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Hörtest – Stichprobenauswahl

**Files:**
- Create: `generator/drova_voice/jsonl.py`, `generator/drova_voice/bakeoff.py` (erster Teil)
- Test: `generator/tests/test_bakeoff_select.py`

**Interfaces:**
- Consumes: `read_loc_file` (Task 4), `build_speech_text`, `STAGE_RE`, `GVAR_RE` (Task 5), `NAME_TOKEN`, `make_name_variants` (Task 6), `from_stage_directions` (Task 7)
- Produces: `write_jsonl(path: Path, rows: Iterable[dict]) -> None`, `read_jsonl(path: Path) -> list[dict]`; in `bakeoff.py`: `BUCKETS`, `BAKEOFF_GVAR_FALLBACK = "zehn"`, `Sample` (frozen: `sample_id`, `source`, `key`, `raw`, `text`, `emotion: dict`, `bucket`; `to_dict()`, `Sample.from_dict(d)`), `classify(raw: str) -> str`, `select_samples(loc_dir: Path, per_bucket: int = 4, seed: int = 42) -> list[Sample]`.

- [ ] **Step 1: Failing test schreiben** – `generator/tests/test_bakeoff_select.py`

```python
from drova_voice.bakeoff import Sample, classify, select_samples
from drova_voice.jsonl import read_jsonl, write_jsonl
from drova_voice.player_name import NAME_TOKEN

LOC = "\n\n".join([
    "Plh_1 { Hmpf. }",
    "Plh_2 { " + "Dies ist ein recht langer Testsatz. " * 8 + "}",
    "Plh_3 { *seufzt* Na gut, dann eben. }",
    f"Plh_4 {{ Danke, {NAME_TOKEN}. Bis bald. }}",
    "Plh_5 { Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen. }",
    "Plh_6 { Wem gehört dieser Hof eigentlich? }",
    "Plh_7 { Verschwinde sofort von hier! }",
    "Plh_8 { Ich habe heute viel zu tun gehabt. }",
    "Plh_9 { *grinst* }",
]) + "\n"


def make_loc_dir(tmp_path):
    d = tmp_path / "de" / "Dialog"
    d.mkdir(parents=True)
    (d / "NPC_Test_de.loc").write_text(LOC, encoding="utf-8")
    return tmp_path / "de"


def test_classify():
    assert classify("Hmpf.") == "short"
    assert classify(f"Hallo {NAME_TOKEN}!") == "player_name"
    assert classify("Hier $GVAR:A.B$ Münzen.") == "gvar"
    assert classify("*seufzt* Ja.") == "stage"
    assert classify("Was ist hier eigentlich los?") == "question"
    assert classify("Verschwinde sofort von hier!") == "exclaim"
    assert classify("Ich habe heute viel zu tun.") == "normal"


def test_select_one_per_bucket_with_prepared_text(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=1)
    by_bucket = {s.bucket: s for s in samples}
    assert set(by_bucket) == {"short", "long", "stage", "player_name", "gvar", "question", "exclaim", "normal"}
    assert by_bucket["player_name"].text == "Danke, Arden. Bis bald."
    assert by_bucket["gvar"].text == "Heute sind zehn Münzen."
    assert by_bucket["stage"].text == "Na gut, dann eben."
    assert by_bucket["stage"].emotion["events"] == [{"tag": "sigh", "pos": 0}]
    assert all(s.text.strip() for s in samples)


def test_stage_only_line_is_never_selected(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=10)
    assert all(s.key != "Plh_9" for s in samples)


def test_selection_is_deterministic(tmp_path):
    d = make_loc_dir(tmp_path)
    assert select_samples(d, per_bucket=1) == select_samples(d, per_bucket=1)


def test_jsonl_roundtrip(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=1)
    path = tmp_path / "out" / "samples.jsonl"
    write_jsonl(path, (s.to_dict() for s in samples))
    assert [Sample.from_dict(d) for d in read_jsonl(path)] == samples
```

Hinweis: Die Zeile „Plh_2“ ist ≥ 200 Zeichen (Bucket `long`); `Plh_9` ist nur Regieanweisung und muss übersprungen werden.

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_bakeoff_select.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren**

`generator/drova_voice/jsonl.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
```

`generator/drova_voice/bakeoff.py` (erster Teil):
```python
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

from drova_voice.emotions import from_stage_directions
from drova_voice.loc import read_loc_file
from drova_voice.player_name import NAME_TOKEN, make_name_variants
from drova_voice.speech_text import GVAR_RE, STAGE_RE, SpeechText, build_speech_text

BUCKETS = ("short", "long", "stage", "player_name", "gvar", "question", "exclaim", "normal")
BAKEOFF_GVAR_FALLBACK = "zehn"


@dataclass(frozen=True)
class Sample:
    sample_id: str
    source: str
    key: str
    raw: str
    text: str
    emotion: dict
    bucket: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Sample":
        return cls(**d)


def classify(raw: str) -> str:
    if NAME_TOKEN in raw:
        return "player_name"
    if "$GVAR:" in raw:
        return "gvar"
    if STAGE_RE.search(raw):
        return "stage"
    plain = raw.strip()
    if len(plain) <= 12:
        return "short"
    if len(plain) >= 200:
        return "long"
    if plain.endswith("?"):
        return "question"
    if plain.endswith("!"):
        return "exclaim"
    return "normal"


def _prepare(raw: str) -> SpeechText:
    prepared = make_name_variants(raw).arden if NAME_TOKEN in raw else raw
    values = {name: BAKEOFF_GVAR_FALLBACK for name in GVAR_RE.findall(prepared)}
    return build_speech_text(prepared, values)


def select_samples(loc_dir: Path, per_bucket: int = 4, seed: int = 42) -> list[Sample]:
    # Nicht sprechbare Zeilen (z. B. nur "*grinst*") gar nicht erst in den Pool,
    # sonst könnte ein Bucket je nach Zufall leer bleiben.
    pool: dict[str, list[tuple[str, str, str, SpeechText]]] = {b: [] for b in BUCKETS}
    for f in sorted((Path(loc_dir) / "Dialog").glob("NPC_*.loc")):
        for e in read_loc_file(f).entries:
            if not e.text.strip():
                continue
            st = _prepare(e.text)
            if st.is_speakable:
                pool[classify(e.text)].append((f.stem, e.key, e.text, st))
    rng = random.Random(seed)
    samples: list[Sample] = []
    for bucket in BUCKETS:
        candidates = pool[bucket]
        for source, key, raw, st in rng.sample(candidates, min(per_bucket, len(candidates))):
            tag = from_stage_directions(st.stage)
            samples.append(Sample(f"{bucket}_{len(samples):02d}", source, key, raw, st.text, tag.to_dict(), bucket))
    return samples
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_bakeoff_select.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add generator/drova_voice/jsonl.py generator/drova_voice/bakeoff.py generator/tests/test_bakeoff_select.py
git commit -m "Add bake-off sample selection" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Hörtest – Lauf, Hörseite, CLI

**Files:**
- Modify: `generator/drova_voice/bakeoff.py` (zweiter Teil anhängen)
- Create: `generator/drova_voice/cli.py`, `generator/bakeoff_voices.yaml`
- Test: `generator/tests/test_bakeoff_run.py`, `generator/tests/test_cli.py`

**Interfaces:**
- Consumes: `Sample` (Task 10), `EngineClient`, `worker_command`, `SynthRequest`, `SynthResponse` (Task 9), `render_request` (Task 8), `EmotionTag` (Task 7), `load_config`, `DEFAULT_CONFIG_PATH` (Task 1), `read_jsonl`, `write_jsonl` (Task 10)
- Produces: `VoiceSpec` (frozen: `engine: str`, `voice: str | None = None`, `reference: str | None = None`; Property `slug`), `BakeoffResult` (frozen: `engine`, `voice_slug`, `sample_id`, `ok: bool`, `wav: str | None`, `duration: float | None`, `seconds: float`, `error: str | None`; `to_dict()`, `from_dict()`), `load_voice_specs(path: Path, repo_root: Path) -> list[VoiceSpec]`, `run_bakeoff(samples, voices, client_factory: Callable[[str], ContextManager], out_dir: Path) -> list[BakeoffResult]`, `write_sheet(samples, results, out_dir: Path) -> Path`, `REF_TEXT: str`; CLI `drova-voice bakeoff select|run|sheet|refs`, `drova-voice smoke <engine>`; `cli.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Failing tests schreiben**

`generator/tests/test_bakeoff_run.py`:
```python
from pathlib import Path

from drova_voice.bakeoff import BakeoffResult, Sample, VoiceSpec, run_bakeoff, write_sheet
from drova_voice.engines.protocol import SynthResponse

SAMPLES = [
    Sample("short_00", "NPC_A_de", "Plh_1", "Hmpf.", "Hmpf.", {"emotion": "neutral", "intensity": 0.0, "events": [], "emphasis": [], "notes": [], "source": "default"}, "short"),
    Sample("stage_01", "NPC_A_de", "Plh_2", "*seufzt* Na <gut>.", "Na gut & so.", {"emotion": "neutral", "intensity": 0.0, "events": [{"tag": "sigh", "pos": 0}], "emphasis": [], "notes": [], "source": "stage"}, "stage"),
]


class FakeClient:
    def __init__(self):
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def synth(self, req):
        self.requests.append(req)
        Path(req.out_path).write_bytes(b"RIFF")
        return SynthResponse(id=req.id, ok=True, out_path=req.out_path, sample_rate=22050, duration=1.0)


def test_voice_slug():
    assert VoiceSpec("xtts", voice="Ana Florence").slug == "ana-florence"
    assert VoiceSpec("chatterbox", reference="voices/bakeoff/xtts-viktor-eka.wav").slug == "xtts-viktor-eka"
    assert VoiceSpec("chatterbox").slug == "default"


def test_run_writes_final_files_and_renders_per_engine(tmp_path):
    client = FakeClient()
    results = run_bakeoff(SAMPLES, [VoiceSpec("kitten", voice="German")], lambda engine: client, tmp_path)
    assert all(r.ok for r in results)
    assert (tmp_path / "kitten" / "german" / "short_00.wav").exists()
    assert not list(tmp_path.rglob("*.part.wav"))
    assert client.requests[1].text == "<sigh> Na gut & so."


def test_resume_skips_finished_and_ignores_partial(tmp_path):
    run_bakeoff(SAMPLES[:1], [VoiceSpec("fake")], lambda e: FakeClient(), tmp_path)
    stale = tmp_path / "fake" / "default" / "stage_01.part.wav"
    stale.write_bytes(b"halb")
    client = FakeClient()
    results = run_bakeoff(SAMPLES, [VoiceSpec("fake")], lambda e: client, tmp_path)
    assert [r.id for r in client.requests] == ["fake/default/stage_01"]
    assert (tmp_path / "fake" / "default" / "stage_01.wav").exists()
    assert len(results) == 2


def test_failed_synth_leaves_no_file(tmp_path):
    class Failing(FakeClient):
        def synth(self, req):
            Path(req.out_path).write_bytes(b"x")
            return SynthResponse(id=req.id, ok=False, error="kaputt")
    results = run_bakeoff(SAMPLES[:1], [VoiceSpec("fake")], lambda e: Failing(), tmp_path)
    assert not results[0].ok and results[0].error == "kaputt"
    assert not list((tmp_path / "fake").rglob("*.wav"))


def test_sheet_escapes_text_and_links_audio(tmp_path):
    results = [
        BakeoffResult("fake", "default", "short_00", True, str(tmp_path / "fake" / "default" / "short_00.wav"), 1.0, 0.5, None),
        BakeoffResult("fake", "default", "stage_01", False, None, None, 0.1, "kaputt"),
    ]
    html = write_sheet(SAMPLES, results, tmp_path).read_text(encoding="utf-8")
    assert 'src="fake/default/short_00.wav"' in html
    assert "Na gut &amp; so." in html
    assert "kaputt" in html
    assert "0.50" in html  # Echtzeitfaktor 0.5 s / 1.0 s
```

`generator/tests/test_cli.py`:
```python
from drova_voice.cli import main
from drova_voice.jsonl import read_jsonl


def test_bakeoff_select_and_run_with_fake_engine(tmp_path):
    repo = tmp_path / "repo"
    gen = repo / "generator"
    gen.mkdir(parents=True)
    game = tmp_path / "game"
    dialog = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    dialog.mkdir(parents=True)
    (dialog / "NPC_A_de.loc").write_text("Plh_1 { Wem gehört dieser Hof eigentlich? }\n", encoding="utf-8")
    cfg = gen / "config.yaml"
    cfg.write_text(f'game_dir: "{game.as_posix()}"\n', encoding="utf-8")
    voices = gen / "voices.yaml"
    voices.write_text("- {engine: fake}\n", encoding="utf-8")

    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    samples = read_jsonl(repo / "data" / "bakeoff" / "samples.jsonl")
    assert [s["bucket"] for s in samples] == ["question"]

    assert main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices)]) == 0
    assert (repo / "out" / "bakeoff" / "fake" / "default" / "question_00.wav").exists()
    assert (repo / "out" / "bakeoff" / "index.html").exists()
```

Hinweis: Der CLI-Test braucht den Fake-Worker aus `generator/workers/fake`. `cli.py` sucht Worker daher immer im **Paket-Repo** (`Path(__file__).parents[1] / "workers"`), nicht im `repo_root` der Config.

- [ ] **Step 2: Tests laufen lassen, müssen fehlschlagen**

Run: `cd generator && .venv/Scripts/python -m pytest tests/test_bakeoff_run.py tests/test_cli.py -v`
Expected: FAIL (`ImportError: cannot import name 'BakeoffResult'` bzw. `No module named 'drova_voice.cli'`)

- [ ] **Step 3: `bakeoff.py` erweitern** (an das Ende der Datei anhängen; Imports oben ergänzen)

Zusätzliche Imports oben in `bakeoff.py`:
```python
import html
import re
import time
from typing import Callable, ContextManager, Sequence

import yaml

from drova_voice.emotions import EmotionTag
from drova_voice.engines.protocol import SynthRequest
from drova_voice.render import render_request
```

Anhängen:
```python
REF_TEXT = (
    "Ich bin schon lange in diesen Wäldern unterwegs. Manchmal frage ich mich, "
    "ob der Weg wirklich lohnt. Doch der Morgen ist klar, und ich bleibe."
)


@dataclass(frozen=True)
class VoiceSpec:
    engine: str
    voice: str | None = None
    reference: str | None = None

    @property
    def slug(self) -> str:
        base = self.voice or (Path(self.reference).stem if self.reference else "default")
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "default"


@dataclass(frozen=True)
class BakeoffResult:
    engine: str
    voice_slug: str
    sample_id: str
    ok: bool
    wav: str | None
    duration: float | None
    seconds: float
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BakeoffResult":
        return cls(**d)


def load_voice_specs(path: Path, repo_root: Path) -> list[VoiceSpec]:
    specs = []
    for item in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []:
        ref = item.get("reference")
        if ref and not Path(ref).is_absolute():
            ref = str((Path(repo_root) / ref).resolve())
        specs.append(VoiceSpec(item["engine"], item.get("voice"), ref))
    return specs


def run_bakeoff(
    samples: Sequence[Sample],
    voices: Sequence[VoiceSpec],
    client_factory: Callable[[str], ContextManager],
    out_dir: Path,
) -> list[BakeoffResult]:
    results: list[BakeoffResult] = []
    for engine in dict.fromkeys(v.engine for v in voices):
        engine_voices = [v for v in voices if v.engine == engine]
        todo = [(v, s) for v in engine_voices for s in samples
                if not (Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav").exists()]
        for v in engine_voices:
            for s in samples:
                wav = Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav"
                if wav.exists():
                    results.append(BakeoffResult(engine, v.slug, s.sample_id, True, str(wav), None, 0.0, None))
        if not todo:
            continue
        with client_factory(engine) as client:
            for v, s in todo:
                wav = Path(out_dir) / engine / v.slug / f"{s.sample_id}.wav"
                part = wav.with_name(f"{s.sample_id}.part.wav")
                wav.parent.mkdir(parents=True, exist_ok=True)
                text, params = render_request(engine, s.text, EmotionTag.from_dict(s.emotion))
                started = time.perf_counter()
                resp = client.synth(SynthRequest(
                    id=f"{engine}/{v.slug}/{s.sample_id}", text=text, out_path=str(part),
                    voice=v.voice, reference=v.reference, params=params,
                ))
                seconds = time.perf_counter() - started
                if resp.ok:
                    part.replace(wav)
                    results.append(BakeoffResult(engine, v.slug, s.sample_id, True, str(wav), resp.duration, seconds, None))
                else:
                    part.unlink(missing_ok=True)
                    results.append(BakeoffResult(engine, v.slug, s.sample_id, False, None, None, seconds, resp.error))
    return results


def write_sheet(samples: Sequence[Sample], results: Sequence[BakeoffResult], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    by_key = {(r.engine, r.voice_slug, r.sample_id): r for r in results}
    columns = sorted({(r.engine, r.voice_slug) for r in results})
    esc = html.escape
    head = "".join(f"<th>{esc(e)}<br><small>{esc(v)}</small></th>" for e, v in columns)
    rows = []
    for s in samples:
        cells = []
        for e, v in columns:
            r = by_key.get((e, v, s.sample_id))
            if r and r.ok and r.wav:
                src = Path(r.wav).resolve().relative_to(out_dir.resolve()).as_posix()
                cells.append(f'<td><audio controls preload="none" src="{esc(src)}"></audio></td>')
            else:
                cells.append(f"<td>– {esc(r.error) if r and r.error else ''}</td>")
        emo = s.emotion.get("emotion", "neutral")
        events = ", ".join(ev["tag"] for ev in s.emotion.get("events", []))
        rows.append(f"<tr><td><b>{esc(s.bucket)}</b><br>{esc(s.text)}<br><small>{esc(emo)} {esc(events)} · {esc(s.source)}/{esc(s.key)}</small></td>{''.join(cells)}</tr>")
    summary = []
    for e, v in columns:
        timed = [r for r in results if (r.engine, r.voice_slug) == (e, v) and r.ok and r.duration]
        dur = sum(r.duration for r in timed)
        sec = sum(r.seconds for r in timed)
        rtf = f"{sec / dur:.2f}" if dur else "–"
        summary.append(f"<tr><td>{esc(e)} / {esc(v)}</td><td>{dur:.1f} s</td><td>{sec:.1f} s</td><td>{rtf}</td></tr>")
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>DrovaVoice Hörtest</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}audio{{width:220px}}</style>
</head><body><h1>DrovaVoice Hörtest</h1>
<h2>Geschwindigkeit</h2><table><tr><th>Engine / Stimme</th><th>Audio</th><th>Rechenzeit</th><th>Echtzeitfaktor</th></tr>{''.join(summary)}</table>
<h2>Zeilen</h2><table><tr><th>Zeile</th>{head}</tr>{''.join(rows)}</table></body></html>"""
    path = out_dir / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
```

- [ ] **Step 4: CLI implementieren** – `generator/drova_voice/cli.py`

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from drova_voice.bakeoff import (REF_TEXT, BakeoffResult, Sample, VoiceSpec, load_voice_specs,
                                 run_bakeoff, select_samples, write_sheet)
from drova_voice.config import DEFAULT_CONFIG_PATH, load_config
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineClient, worker_command
from drova_voice.engines.protocol import SynthRequest
from drova_voice.jsonl import read_jsonl, write_jsonl
from drova_voice.render import render_request

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
DEFAULT_VOICES = Path(__file__).resolve().parents[1] / "bakeoff_voices.yaml"


def _client(engine: str) -> EngineClient:
    return EngineClient(worker_command(WORKERS_DIR, engine))


def _merge_results(path: Path, new: list[BakeoffResult]) -> list[BakeoffResult]:
    merged = {}
    if path.exists():
        for d in read_jsonl(path):
            r = BakeoffResult.from_dict(d)
            merged[(r.engine, r.voice_slug, r.sample_id)] = r
    for r in new:
        old = merged.get((r.engine, r.voice_slug, r.sample_id))
        if r.seconds == 0.0 and old is not None and old.ok:
            continue  # übersprungene Datei: gemessene Werte behalten
        merged[(r.engine, r.voice_slug, r.sample_id)] = r
    results = list(merged.values())
    write_jsonl(path, (r.to_dict() for r in results))
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="drova-voice")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    sub = p.add_subparsers(dest="cmd", required=True)
    bake = sub.add_parser("bakeoff", help="TTS-Hörtest").add_subparsers(dest="bcmd", required=True)
    sel = bake.add_parser("select", help="Stichprobe aus den .loc-Dateien ziehen")
    sel.add_argument("--per-bucket", type=int, default=4)
    run = bake.add_parser("run", help="Stichprobe mit allen Stimmen erzeugen")
    run.add_argument("--voices", type=Path, default=DEFAULT_VOICES)
    run.add_argument("--engine", action="append", help="nur diese Engine(s)")
    bake.add_parser("sheet", help="Hörseite neu schreiben")
    refs = bake.add_parser("refs", help="Referenzstimmen mit XTTS-Sprechern erzeugen")
    refs.add_argument("--speaker", action="append", required=True)
    smoke = sub.add_parser("smoke", help="Engine mit einem Testsatz prüfen")
    smoke.add_argument("engine")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    bake_data = cfg.data_dir / "bakeoff"
    bake_out = cfg.out_dir / "bakeoff"
    samples_path = bake_data / "samples.jsonl"
    results_path = bake_out / "results.jsonl"

    if args.cmd == "smoke":
        out = cfg.out_dir / "smoke" / f"{args.engine}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        text, params = render_request(args.engine, "Hallo, ich bin ein Test der Sprachausgabe.", EmotionTag())
        with _client(args.engine) as client:
            resp = client.synth(SynthRequest(id="smoke", text=text, out_path=str(out), params=params))
        print(f"{args.engine}: {'OK' if resp.ok else 'FEHLER'} {resp.duration or ''} {resp.error or ''} → {out}")
        return 0 if resp.ok else 1

    if args.bcmd == "select":
        samples = select_samples(cfg.loc_dir, per_bucket=args.per_bucket)
        write_jsonl(samples_path, (s.to_dict() for s in samples))
        print(f"{len(samples)} Zeilen → {samples_path}")
        return 0

    samples = [Sample.from_dict(d) for d in read_jsonl(samples_path)]

    if args.bcmd == "refs":
        target = cfg.voices_dir / "bakeoff"
        target.mkdir(parents=True, exist_ok=True)
        with _client("xtts") as client:
            for speaker in args.speaker:
                slug = VoiceSpec("xtts", voice=speaker).slug
                out = target / f"xtts-{slug}.wav"
                resp = client.synth(SynthRequest(id=slug, text=REF_TEXT, out_path=str(out), voice=speaker))
                print(f"{speaker}: {'OK' if resp.ok else resp.error} → {out}")
        return 0

    if args.bcmd == "run":
        voices = load_voice_specs(args.voices, cfg.repo_root)
        if args.engine:
            voices = [v for v in voices if v.engine in args.engine]
        new = run_bakeoff(samples, voices, _client, bake_out)
        results = _merge_results(results_path, new)
        failed = [r for r in new if not r.ok]
        for r in failed:
            print(f"FEHLER {r.engine}/{r.voice_slug}/{r.sample_id}: {r.error}", file=sys.stderr)
    else:  # sheet
        results = [BakeoffResult.from_dict(d) for d in read_jsonl(results_path)] if results_path.exists() else []

    page = write_sheet(samples, results, bake_out)
    print(f"Hörseite: {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Stimmenliste anlegen** – `generator/bakeoff_voices.yaml`

```yaml
# Stimmen für den Hörtest. reference: Pfad relativ zur Repo-Wurzel (voices/ ist gitignored).
- {engine: kitten, voice: German}
- {engine: chatterbox}                      # Standardstimme mit language_id=de
- {engine: xtts, voice: "Ana Florence"}
- {engine: xtts, voice: "Viktor Eka"}
- {engine: xtts, voice: "Damien Black"}
# Nach `drova-voice bakeoff refs --speaker "Viktor Eka" --speaker "Ana Florence"`:
# - {engine: kitten, reference: voices/bakeoff/xtts-viktor-eka.wav}
# - {engine: chatterbox, reference: voices/bakeoff/xtts-viktor-eka.wav}
# - {engine: chatterbox, reference: voices/bakeoff/xtts-ana-florence.wav}
```

- [ ] **Step 6: Tests laufen lassen**

Run: `cd generator && .venv/Scripts/python -m pytest -v`
Expected: alle Tests grün (Task 1–11).

- [ ] **Step 7: Echte Stichprobe ziehen**

Run: `cd generator && .venv/Scripts/drova-voice bakeoff select`
Expected: `32 Zeilen → …/data/bakeoff/samples.jsonl` (± einige, falls ein Bucket kleiner ist). Datei kurz ansehen: Texte ohne `*…*`, ohne `$GVAR`, Spielername als „Arden“.

- [ ] **Step 8: Commit**

```bash
git add generator/drova_voice/bakeoff.py generator/drova_voice/cli.py generator/bakeoff_voices.yaml generator/tests/test_bakeoff_run.py generator/tests/test_cli.py
git commit -m "Add bake-off runner, listening sheet and CLI" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Engine-Worker Kitten, Chatterbox, XTTS (Freigabe nötig)

**Files:**
- Create: `generator/workers/kitten/{worker.py,requirements.txt,README.md}`, `generator/workers/chatterbox/{worker.py,requirements.txt,README.md}`, `generator/workers/xtts/{worker.py,requirements.txt,README.md}`

**Interfaces:**
- Consumes: `serve(...)` aus `workers/_common/worker_loop.py` (Task 9); Anfrage-Felder `text`, `out_path`, `voice`, `reference`, `params` (Task 9); `render_request` liefert für Kitten fertigen Tag-Text, für Chatterbox `params.exaggeration`/`params.cfg_weight` (Task 8).
- Produces: lauffähige Worker, aufrufbar über `drova-voice smoke <engine>`.

- [ ] **Step 1: Freigabe beim Nutzer einholen (Hauptsitzung, nicht Subagent)**

Dem Nutzer vorlegen und auf ein klares „ja“ warten:
- Python 3.11 (von uv verwaltet, ca. 30 MB), falls nicht vorhanden
- je Worker-venv: torch 2.6.0 + torchaudio 2.6.0 cu124 von `download.pytorch.org` (ca. 2,5 GB pro venv, 3 venvs)
- Pakete von PyPI: `kittenml`, `soundfile`; `chatterbox-tts`; `coqui-tts`
- Modelle von Hugging Face beim ersten Start: KittenTTS 2 (ca. 1 GB), Chatterbox Multilingual (ca. 2–3 GB), XTTS-v2 (ca. 1,8 GB)
- XTTS-v2: Der Nutzer muss der **Coqui Public Model License (CPML, nur nicht-kommerziell)** selbst zustimmen (https://coqui.ai/cpml). Erst danach wird `COQUI_TOS_AGREED=1` gesetzt.

- [ ] **Step 2: Kitten-Worker anlegen**

`generator/workers/kitten/requirements.txt`:
```
kittenml
soundfile
```

`generator/workers/kitten/README.md`:
```markdown
# Kitten TTS 2 Worker

uv venv --python 3.11 .venv
uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
uv pip install --python .venv -r requirements.txt

Lizenz des Modells: Stellon Labs Community License (Namensnennung erforderlich).
```

`generator/workers/kitten/worker.py`:
```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

MODEL = "KittenML/kitten-tts-2"


def load():
    from kittenml import KittenTTS
    return KittenTTS(MODEL)


def synth(model, req: dict) -> tuple[int, float]:
    import soundfile as sf

    kwargs = {"normalize": False}
    if req.get("reference"):
        kwargs["reference"] = req["reference"]
    else:
        kwargs["voice"] = req.get("voice") or "German"
    audio = model.generate(req["text"], **kwargs)
    sf.write(req["out_path"], audio, model.sample_rate)
    return int(model.sample_rate), len(audio) / model.sample_rate


if __name__ == "__main__":
    serve("kitten", MODEL, load, synth)
```

- [ ] **Step 3: Kitten installieren und API prüfen**

Run:
```bash
cd generator/workers/kitten && uv venv --python 3.11 .venv \
 && uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 \
 && uv pip install --python .venv -r requirements.txt \
 && .venv/Scripts/python -c "import inspect, kittenml; print(inspect.signature(kittenml.KittenTTS.generate)); import torch; print('cuda', torch.cuda.is_available())"
```
Expected: Signatur enthält `voice`, `reference`, `normalize` (o. ä.); `cuda True`. **Weicht die Signatur ab** (z. B. anderer Parametername oder Rückgabe als Tensor): `synth()` an die tatsächliche API anpassen und das im Commit vermerken.

- [ ] **Step 4: Kitten Smoke-Test**

Run: `cd generator && .venv/Scripts/drova-voice smoke kitten`
Expected: `kitten: OK <dauer> → …/out/smoke/kitten.wav`; Datei anhören (deutsch verständlich?).

- [ ] **Step 5: Chatterbox-Worker anlegen**

`generator/workers/chatterbox/requirements.txt`:
```
chatterbox-tts
```

`generator/workers/chatterbox/README.md`:
```markdown
# Chatterbox Multilingual Worker

uv venv --python 3.11 .venv
uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
uv pip install --python .venv -r requirements.txt

Lizenz: MIT.
```

`generator/workers/chatterbox/worker.py`:
```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

MODEL = "ResembleAI/chatterbox-multilingual"


def load():
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return ChatterboxMultilingualTTS.from_pretrained(device=device)


def synth(model, req: dict) -> tuple[int, float]:
    import torchaudio

    params = req.get("params") or {}
    kwargs = {
        "language_id": "de",
        "exaggeration": float(params.get("exaggeration", 0.5)),
        "cfg_weight": float(params.get("cfg_weight", 0.5)),
    }
    if req.get("reference"):
        kwargs["audio_prompt_path"] = req["reference"]
    wav = model.generate(req["text"], **kwargs)
    torchaudio.save(req["out_path"], wav.cpu(), model.sr)
    return int(model.sr), wav.shape[-1] / model.sr


if __name__ == "__main__":
    serve("chatterbox", MODEL, load, synth)
```

- [ ] **Step 6: Chatterbox installieren, API prüfen, Smoke-Test**

Run:
```bash
cd generator/workers/chatterbox && uv venv --python 3.11 .venv \
 && uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 \
 && uv pip install --python .venv -r requirements.txt \
 && .venv/Scripts/python -c "import inspect; from chatterbox.mtl_tts import ChatterboxMultilingualTTS as M; print(inspect.signature(M.generate)); import torch; print('cuda', torch.cuda.is_available())"
cd ../.. && .venv/Scripts/drova-voice smoke chatterbox
```
Expected: Signatur mit `language_id`, `audio_prompt_path`, `exaggeration`, `cfg_weight`; `cuda True`; `chatterbox: OK`. Bei Abweichung `synth()` anpassen. Falls uv torch durch eine CPU-Version ersetzt (`cuda False`): torch-Installationsbefehl nach dem `-r requirements.txt` wiederholen.

- [ ] **Step 7: XTTS-Worker anlegen**

`generator/workers/xtts/requirements.txt`:
```
coqui-tts
soundfile
```

`generator/workers/xtts/README.md`:
```markdown
# XTTS-v2 Worker (Coqui, Idiap-Fork)

Lizenz des Modells: Coqui Public Model License (CPML) – nur nicht-kommerzielle Nutzung.
Vor der ersten Nutzung selbst zustimmen und dann `export COQUI_TOS_AGREED=1` setzen.

uv venv --python 3.11 .venv
uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
uv pip install --python .venv -r requirements.txt
```

`generator/workers/xtts/worker.py`:
```python
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from worker_loop import serve  # noqa: E402

MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"


def load():
    if os.environ.get("COQUI_TOS_AGREED") != "1":
        raise RuntimeError("CPML nicht bestätigt: COQUI_TOS_AGREED=1 setzen (siehe README)")
    import torch
    from TTS.api import TTS
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return TTS(MODEL).to(device)


def synth(tts, req: dict) -> tuple[int, float]:
    import numpy as np
    import soundfile as sf

    kwargs = {"language": "de"}
    if req.get("reference"):
        kwargs["speaker_wav"] = req["reference"]
    else:
        kwargs["speaker"] = req.get("voice") or "Ana Florence"
    wav = np.asarray(tts.tts(text=req["text"], **kwargs), dtype=np.float32)
    rate = int(tts.synthesizer.output_sample_rate)
    sf.write(req["out_path"], wav, rate)
    return rate, len(wav) / rate


if __name__ == "__main__":
    serve("xtts", MODEL, load, synth)
```

- [ ] **Step 8: XTTS installieren (erst nach CPML-Zustimmung des Nutzers), Sprecher prüfen, Smoke-Test**

Run:
```bash
cd generator/workers/xtts && uv venv --python 3.11 .venv \
 && uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 \
 && uv pip install --python .venv -r requirements.txt
cd ../.. && export COQUI_TOS_AGREED=1 && .venv/Scripts/drova-voice smoke xtts
COQUI_TOS_AGREED=1 workers/xtts/.venv/Scripts/python -c "from TTS.api import TTS; t=TTS('tts_models/multilingual/multi-dataset/xtts_v2'); print(t.speakers)"
```
Expected: `xtts: OK`; Liste der eingebauten Sprecher. Prüfen, dass „Ana Florence“, „Viktor Eka“, „Damien Black“ enthalten sind; sonst `bakeoff_voices.yaml` auf vorhandene Namen ändern.

- [ ] **Step 9: Commit**

```bash
git add generator/workers/kitten generator/workers/chatterbox generator/workers/xtts generator/bakeoff_voices.yaml
git commit -m "Add Kitten, Chatterbox and XTTS engine workers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Hörtest durchführen und Entscheidung festhalten (M2)

**Files:**
- Create: `docs/decisions/2026-10-tts-engine.md`

**Interfaces:**
- Consumes: CLI aus Task 11, Worker aus Task 12.

- [ ] **Step 1: Referenzstimmen erzeugen**

Run: `cd generator && export COQUI_TOS_AGREED=1 && .venv/Scripts/drova-voice bakeoff refs --speaker "Viktor Eka" --speaker "Ana Florence" --speaker "Damien Black"`
Expected: drei WAVs unter `voices/bakeoff/`.

- [ ] **Step 2: Klon-Varianten aktivieren**

In `generator/bakeoff_voices.yaml` die auskommentierten `reference:`-Zeilen aktivieren (Kitten + Chatterbox mit `xtts-viktor-eka.wav` und `xtts-ana-florence.wav`).

- [ ] **Step 3: Hörtest laufen lassen**

Run: `cd generator && export COQUI_TOS_AGREED=1 && .venv/Scripts/drova-voice bakeoff run`
Expected: `Hörseite: …/out/bakeoff/index.html`; keine oder nur einzelne `FEHLER`-Zeilen. Bei Fehlern: Fehlermeldung lesen, Worker korrigieren, erneut starten (fertige Dateien werden übersprungen).

- [ ] **Step 4: Nutzer hört und bewertet**

Dem Nutzer `out/bakeoff/index.html` zum Öffnen im Browser geben. Bewertungsfragen:
1. Klingt Deutsch natürlich (Aussprache, Betonung, kein Akzent)?
2. Wirken die Emotionen (Bucket `stage`, `exclaim`, `question`)?
3. Funktionieren kurze Zeilen (`short`) ohne Artefakte?
4. Wie unterscheidbar/gut sind geklonte Stimmen (Referenz `xtts-*`)?
5. Echtzeitfaktor → hochgerechnete Zeit für ≈ 22 h Audio.

- [ ] **Step 5: Entscheidung dokumentieren** – `docs/decisions/2026-10-tts-engine.md`

Vorlage (vom Nutzer ausfüllen lassen bzw. mit seinen Antworten befüllen):
```markdown
# Entscheidung: TTS-Engine und Stimmen-Quelle

Datum: 
Getestet: Kitten TTS 2 (German + Klon), Chatterbox Multilingual (Standard + Klon), XTTS-v2 (3 Sprecher)

| Kriterium | Kitten | Chatterbox | XTTS |
|---|---|---|---|
| Deutsch natürlich (1–5) | | | |
| Emotionen (1–5) | | | |
| Kurze Zeilen (1–5) | | | |
| Klonqualität (1–5) | | | |
| Echtzeitfaktor | | | |
| Hochrechnung 22 h Audio | | | |

**Gewählte Engine:**
**Stimmen-Quelle für den Pool:** (eingebaute Stimmen / XTTS-Sprecher als Referenz / Common Voice / eigene Aufnahmen)
**Begründung:**
**Folgen für Plan 2:**
```

- [ ] **Step 6: Commit**

```bash
git add docs/decisions/2026-10-tts-engine.md generator/bakeoff_voices.yaml
git commit -m "Record TTS engine decision from bake-off" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: MelonLoader und Modding API installieren (M0, interaktiv, Freigabe nötig)

**Files:**
- Create: `docs/setup.md`

- [ ] **Step 1: Freigabe beim Nutzer einholen**

Vorlegen und auf „ja“ warten:
- `MelonLoader.x64.zip` v0.7.3 von https://github.com/LavaGang/MelonLoader/releases/tag/v0.7.3 → wird in den Spielordner entpackt (fügt `version.dll`, `MelonLoader/` u. a. hinzu).
- `Modding_API.zip` (245 KB) von https://github.com/Drova-Modding/Drova-Modding-API/releases/tag/release-0.5.4.
- Rückbau: die hinzugefügten Dateien/Ordner löschen (Liste aus Step 3).

- [ ] **Step 2: Herunterladen in einen leeren Scratch-Ordner**

Run:
```bash
DL="$TEMP/drova-dl" && rm -rf "$DL" && mkdir -p "$DL/ml" "$DL/api"
gh release download v0.7.3 -R LavaGang/MelonLoader -p MelonLoader.x64.zip -D "$DL"
gh release download release-0.5.4 -R Drova-Modding/Drova-Modding-API -p Modding_API.zip -D "$DL"
unzip -q "$DL/MelonLoader.x64.zip" -d "$DL/ml" && unzip -q "$DL/Modding_API.zip" -d "$DL/api"
find "$DL/ml" -maxdepth 2 | head -30; find "$DL/api" | head -40
```
Expected: MelonLoader-Inhalt (`version.dll`, `MelonLoader/…`); API-Inhalt mit `Mods/Drova_Modding_API.dll`, `UserLibs/NVorbis.dll` o. ä. Struktur prüfen, bevor kopiert wird.

- [ ] **Step 3: In den Spielordner kopieren und Liste festhalten**

Run:
```bash
GAME="/d/Games/Steam/steamapps/common/Drova - Forsaken Kin"
cp -r "$DL/ml/." "$GAME/"
cp -r "$DL/api/." "$GAME/"   # nur wenn Step 2 zeigt, dass das ZIP bereits Mods/ und UserLibs/ enthält; sonst Dateien gezielt nach Mods/ bzw. UserLibs/ kopieren
ls "$GAME"; ls "$GAME/Mods" "$GAME/UserLibs"
```

- [ ] **Step 4: Spiel einmal starten (Nutzer)**

Nutzer startet Drova über Steam, wartet bis zum Hauptmenü (erster Start dauert wegen der Il2Cpp-Assembly-Erzeugung mehrere Minuten), beendet das Spiel.

Run:
```bash
GAME="/d/Games/Steam/steamapps/common/Drova - Forsaken Kin"
ls "$GAME/MelonLoader/Il2CppAssemblies" | grep -E "Assembly-CSharp|NodeCanvas|Drova" | head
grep -iE "Drova Modding API|error" "$GAME/MelonLoader/Latest.log" | head -20
```
Expected: Il2Cpp-Assemblies vorhanden; Log zeigt, dass „Drova Modding API“ 0.5.4 geladen wurde, keine roten Fehler zur API.

- [ ] **Step 5: `docs/setup.md` schreiben**

```markdown
# Setup Spiel & Mod

Getestet mit: Drova: Forsaken Kin (Steam, Stand 2026-10), Unity 2022.3.45f1, MelonLoader 0.7.3, Drova Modding API 0.5.4.

1. `MelonLoader.x64.zip` (v0.7.3) in den Spielordner entpacken.
2. `Modding_API.zip` (release-0.5.4) in den Spielordner entpacken (`Mods/`, `UserLibs/`).
3. Spiel einmal bis ins Hauptmenü starten (erzeugt `MelonLoader/Il2CppAssemblies`), beenden.
4. Mod bauen: `dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release` (kopiert nach `Mods/` und `UserLibs/`).
   Anderer Spielpfad: Umgebungsvariable `DROVA_GAME_DIR` setzen.

Rückbau: `version.dll`, `MelonLoader/`, `Mods/`, `UserLibs/`, `Plugins/` (falls angelegt) aus dem Spielordner löschen.
```

- [ ] **Step 6: Commit**

```bash
git add docs/setup.md
git commit -m "Document game and mod loader setup" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Mod-Gerüst DrovaVoice lädt im Spiel (M0-Abnahme)

**Files:**
- Create: `mod/DrovaVoice/DrovaVoice.csproj`, `mod/DrovaVoice/DrovaVoiceMod.cs`
- Modify: `mod/DrovaVoice.sln` (Projekt hinzufügen)

**Interfaces:**
- Consumes: `$(DrovaGameDir)` (Task 3), `DrovaVoice.Core.LineIds` (Task 3), installierte MelonLoader/API (Task 14)
- Produces: `DrovaVoice.DrovaVoiceMod : MelonMod` – Grundlage für Plan 2.

- [ ] **Step 1: Projekt anlegen**

`mod/DrovaVoice/DrovaVoice.csproj`:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <Nullable>enable</Nullable>
    <LangVersion>latest</LangVersion>
    <ImplicitUsings>disable</ImplicitUsings>
    <AssemblyName>DrovaVoice</AssemblyName>
    <RootNamespace>DrovaVoice</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="..\DrovaVoice.Core\DrovaVoice.Core.csproj" />
  </ItemGroup>
  <ItemGroup>
    <Reference Include="MelonLoader">
      <HintPath>$(DrovaGameDir)\MelonLoader\net6\MelonLoader.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="Il2CppInterop.Runtime">
      <HintPath>$(DrovaGameDir)\MelonLoader\net6\Il2CppInterop.Runtime.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="Drova_Modding_API">
      <HintPath>$(DrovaGameDir)\Mods\Drova_Modding_API.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
  <Target Name="DeployToGame" AfterTargets="Build" Condition="Exists('$(DrovaGameDir)\Mods')">
    <Copy SourceFiles="$(TargetPath)" DestinationFolder="$(DrovaGameDir)\Mods" />
    <Copy SourceFiles="$(TargetDir)DrovaVoice.Core.dll" DestinationFolder="$(DrovaGameDir)\UserLibs" />
  </Target>
</Project>
```

`mod/DrovaVoice/DrovaVoiceMod.cs`:
```csharp
using DrovaVoice.Core;
using MelonLoader;

[assembly: MelonInfo(typeof(DrovaVoice.DrovaVoiceMod), "DrovaVoice", "0.1.0", "janphi001")]
[assembly: MelonGame("Just2D", "Drova")]
[assembly: MelonAdditionalDependencies("Drova_Modding_API")]

namespace DrovaVoice
{
    public sealed class DrovaVoiceMod : MelonMod
    {
        public override void OnInitializeMelon()
        {
            string probe = LineIds.AudioFileName(LineIds.Statement("DT_Main_NPC_Adela", "Dialog/NPC_Adela", "Plh_5"));
            LoggerInstance.Msg($"DrovaVoice {Info.Version} geladen (Core ok: {probe})");
        }
    }
}
```

Run: `cd mod && dotnet sln add DrovaVoice/DrovaVoice.csproj`

- [ ] **Step 2: Bauen**

Run: `dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release`
Expected: Build erfolgreich; `Mods/DrovaVoice.dll` und `UserLibs/DrovaVoice.Core.dll` im Spielordner. Falls `MelonLoader.dll` nicht unter `MelonLoader\net6\` liegt: tatsächlichen Pfad mit `find "$GAME/MelonLoader" -name MelonLoader.dll` ermitteln und HintPath anpassen.

- [ ] **Step 3: Im Spiel prüfen (Nutzer startet, Hauptmenü reicht)**

Run: `grep -E "DrovaVoice" "/d/Games/Steam/steamapps/common/Drova - Forsaken Kin/MelonLoader/Latest.log"`
Expected: `DrovaVoice 0.1.0 geladen (Core ok: 950774fdbc26dddf.ogg)` – der Hash muss exakt dem Testvektor entsprechen.

- [ ] **Step 4: Commit**

```bash
git add mod/DrovaVoice mod/DrovaVoice.sln
git commit -m "Add DrovaVoice mod skeleton that loads in game" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Nach Plan 1

Mit dem Ergebnis von Task 13 (Engine, Stimmen-Quelle, Echtzeitfaktor) und den Il2Cpp-Assemblies aus Task 14 wird **Plan 2: Export (M1) + Durchstich Adela (M3)** geschrieben. Dort werden die echten Typen (`DialogueTree`, `DS_StatementNode`, `GlobalVarSystem`, `ActorGenderSettings`, Addressables) aus `MelonLoader/Il2CppAssemblies` verwendet.
