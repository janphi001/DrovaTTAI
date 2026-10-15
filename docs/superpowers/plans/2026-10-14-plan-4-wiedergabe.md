# Plan 4: Wiedergabe in der Mod — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adela und Jero sind im Spiel hörbar: NPC-Aussagen und Spieler-Auswahloptionen laufen aus `index.json` synchron zu den Untertiteln, mit Lautstärkereglern (Boost bis 200 %) in `MelonPreferences`.

**Architecture:** Reine Logik (Index lesen, Gain, LRU-Budget, Einstellungen, Einmal-Log) liegt in `DrovaVoice.Core` und ist per xUnit getestet. Eine dünne Il2Cpp-Schicht in `DrovaVoice/Playback` ersetzt den Standard-`IAudioConnector` der Modding API durch einen eigenen, der pro Zeile bei Bedarf lädt (`OnWorldDialogueStatement`), und hängt einen Harmony-Prefix an `DS_MultipleChoiceNode.OnExecute` für die Optionsclips. Das Spiel selbst spielt `statement.audio` ab.

**Tech Stack:** C# net6.0 (Mod, Core), xUnit net8.0 (Tests), MelonLoader 0.7.3, Drova Modding API 0.5.4, NVorbis 0.10.5 (liegt in `UserLibs`), HarmonyLib (MelonLoader), Mono.Cecil nur im Scratchpad zum Lesen von IL.

**Spec:** `docs/superpowers/specs/2026-10-14-plan-4-wiedergabe-design.md` (Befunde zur API in §2). Vertrag zum Dateiformat: `docs/audio-format.md`.

## Global Constraints

- Core bleibt ohne Il2Cpp und ohne Spielverzeichnis baubar (`net6.0`, nur BCL). Alles, was `UnityEngine`/Il2Cpp/NVorbis braucht, liegt in `mod/DrovaVoice/Playback`.
- Ausnahmen in Hooks werden immer abgefangen; die Mod darf das Spiel nie anhalten oder Zeilen ändern, für die es keinen Eintrag gibt (Spec §7).
- Das Dekodieren läuft synchron auf dem Hauptthread; Ladezeiten über 500 ms werden nur gemeldet, der Clip bleibt (Spec §10, geändert nach dem Review).
- 100 % Lautstärke ist bit-genau Identität (kein Begrenzer unter/bei 100 %); über 100 % weicher Begrenzer, Ausgabe nie über ±1,0.
- Einstellungen: `Enabled` (Standard `true`), `DialogVolume` 100 (0–200), `PlayerVolume` 100 (0–200), `AudioLanguage` `de`, `CacheMB` 64 (8–512), `Diagnostics` `false` (Spec §6; `Diagnostics` ist neu, siehe Task 8).
- **`AudioManager` der API erst anfassen, wenn `WorldEventSystemManager.Instance != null`** (siehe Plan-Befund unten), sonst bleibt die Klasse die ganze Sitzung unbrauchbar.
- Keine echten Drova-Texte ins Git (Tests mit erfundenen IDs und Pfaden). Keine Downloads ohne Rückfrage; alles auf Laufwerk D:.
- Antworten und Doku auf Deutsch; Commit-Nachrichten englisch, Imperativ, wie im Repo (`Add …`, `Fix …`), ohne Claude-Trailer.
- Baut die Mod, kopiert das Ziel `DeployToGame` die DLLs in den Spielordner. Dafür muss das Spiel geschlossen sein.

## Plan-Befund (aus der API-IL, nicht in der Spec)

`AudioManager`s statischer Konstruktor erzeugt `new AssetBundleAudioProvider()`, dessen Konstruktor `WorldEventSystemManager.Instance.AreaNameSystem` liest. Im Hauptmenü ist `Instance` noch `null`; die `TypeInitializationException` des Exports (R1-Befunde) kommt genau daher, und ein fehlgeschlagener statischer Konstruktor bleibt in der .NET-Laufzeit dauerhaft kaputt. Deshalb ersetzt die Mod den Connector **erst in `OnUpdate`, sobald `WorldEventSystemManager.Instance != null`** (Prüfung alle 60 Frames), nie in `OnInitializeMelon`. Wird `AudioManager` doch zuerst von der API selbst berührt (nach Spielstand-Laden), ist das unschädlich: unser Ersatz überschreibt danach das statische Feld. Task 11 trägt das in die Spec nach.

## Review Focus

- `index.json` mit Pfaden wie `../x.ogg`, `/abs.ogg`, `C:\x.ogg`, `a\b.ogg` darf nie aus dem Audioordner herausführen (Task 1 testet: Eintrag übersprungen).
- Zeile ohne Loca-Pfad oder Schlüssel (leere Teile) → `LineIds` wirft `ArgumentException`; der Connector fängt das und bleibt stumm (Task 9, Handprüfung im Spiel; Task 1 testet `TryGet` mit leerer/`null`-ID → `false`).
- Boost 200 % bei lauten Samples: nie über ±1,0, 100 % unverändert (Task 2).
- Cache über Budget, während ein Clip läuft: die jüngsten 8 werden nie verdrängt (Task 3).
- Defekte, abgeschnittene oder leere OGG-Datei: `OggDecoder.TryDecode` gibt `false`, wirft nicht (Task 5, Smoke-Test).
- Index mit falscher Sprache oder Version ≠ 1: Fehler mit klarer Meldung, kein Absturz (Task 1; Task 8 schaltet die Vertonung dann ab). Ein UTF-8-BOM entfernt `File.ReadAllText`.

---

## Datei-Struktur

| Datei | Verantwortung |
|---|---|
| `mod/DrovaVoice.Core/AudioIndex.cs` (neu) | `VoiceCategory`, `IndexEntry`, `IndexFormatException`, `AudioIndex` (Parsen, Lookup, Pfadsicherheit) |
| `mod/DrovaVoice.Core/Gain.cs` (neu) | Prozent → Faktor, Anwendung mit weichem Begrenzer |
| `mod/DrovaVoice.Core/ClipBudget.cs` (neu) | LRU-Verwaltung nach Bytes mit geschützten jüngsten Einträgen |
| `mod/DrovaVoice.Core/VoiceSettings.cs` (neu) | validierte Einstellungen, Warnungen |
| `mod/DrovaVoice.Core/OnceLog.cs` (neu) | „jede ID nur einmal loggen“, mit Obergrenze |
| `mod/DrovaVoice.Core.Tests/*Tests.cs` (neu je Datei) | xUnit-Tests zu den fünf Core-Dateien |
| `mod/DrovaVoice/Playback/OggDecoder.cs` (neu) | NVorbis → `float[]`; ohne Il2Cpp, damit im Scratchpad testbar |
| `mod/DrovaVoice/Playback/ClipStore.cs` (neu) | `ClipBudget` + `Dictionary<string, AudioClip>`; zerstört verdrängte Clips |
| `mod/DrovaVoice/Playback/ClipLoader.cs` (neu) | Datei → Gain → `AudioClip`, 500-ms-Grenze |
| `mod/DrovaVoice/Playback/VoiceService.cs` (neu) | Index + Store + Loader + Einmal-Log; `GetClip(id)` |
| `mod/DrovaVoice/Playback/VoiceConnector.cs` (neu) | `IAudioConnector` |
| `mod/DrovaVoice/Playback/ChoiceHook.cs` (neu) | Harmony-Prefix für Auswahlknoten |
| `mod/DrovaVoice/DrovaVoice.csproj` (ändern) | NVorbis-Referenz |
| `mod/DrovaVoice/DrovaVoiceMod.cs` (ändern) | Einstellungen, Service, verzögerter Connector-Ersatz |
| `docs/playback.md` (neu) | Einstellungen, Ablauf, Fehlersuche, Abnahme-Checkliste |

Testbefehl für Core: `dotnet test mod/DrovaVoice.Core.Tests` (aus der Repo-Wurzel). Mod bauen: `dotnet build mod/DrovaVoice -c Release`.

---

### Task 1: AudioIndex (Index lesen, Lookup, Pfadsicherheit)

**Files:**
- Create: `mod/DrovaVoice.Core/AudioIndex.cs`
- Test: `mod/DrovaVoice.Core.Tests/AudioIndexTests.cs`

**Interfaces:**
- Produces:
  - `enum VoiceCategory { Dialog, Player }`
  - `sealed record IndexEntry(string File, double Duration, VoiceCategory Category)`
  - `sealed class IndexFormatException : Exception`
  - `AudioIndex.Parse(string json, string expectedLanguage) -> AudioIndex` (wirft `IndexFormatException`)
  - `AudioIndex.TryGet(string? id, out IndexEntry entry) -> bool`; `AudioIndex.Count`, `AudioIndex.Skipped`
  - `AudioIndex.IsSafeRelativePath(string file) -> bool`, `AudioIndex.ResolvePath(string root, string file) -> string?`, `AudioIndex.CategoryOf(string file) -> VoiceCategory`

- [ ] **Step 1: Write the failing tests**

`mod/DrovaVoice.Core.Tests/AudioIndexTests.cs`:

```csharp
using System.IO;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class AudioIndexTests
    {
        private const string Good = @"{
  ""version"": 1, ""language"": ""de"",
  ""entries"": {
    ""DT_X|Dialog/A|Plh_1"":    {""file"": ""dialog/0123456789abcdef.ogg"", ""duration"": 3.214},
    ""DT_X|Dialog/A|Plh_2|c0"": {""file"": ""player/fedcba9876543210.ogg"", ""duration"": 1.9}
  },
  ""variants"": {}
}";

        [Fact]
        public void ParsesEntriesAndCategories()
        {
            var index = AudioIndex.Parse(Good, "de");
            Assert.Equal(2, index.Count);
            Assert.Equal(0, index.Skipped);
            Assert.True(index.TryGet("DT_X|Dialog/A|Plh_1", out var a));
            Assert.Equal("dialog/0123456789abcdef.ogg", a.File);
            Assert.Equal(3.214, a.Duration, 3);
            Assert.Equal(VoiceCategory.Dialog, a.Category);
            Assert.True(index.TryGet("DT_X|Dialog/A|Plh_2|c0", out var b));
            Assert.Equal(VoiceCategory.Player, b.Category);
        }

        [Fact]
        public void UnknownEmptyAndNullIdsAreMisses()
        {
            var index = AudioIndex.Parse(Good, "de");
            Assert.False(index.TryGet("DT_X|Dialog/A|Plh_9", out _));
            Assert.False(index.TryGet("", out _));
            Assert.False(index.TryGet(null, out _));
        }

        [Fact]
        public void LanguageIsComparedIgnoringCase() =>
            Assert.Equal(2, AudioIndex.Parse(Good, "DE").Count);

        [Fact]
        public void RejectsWrongLanguage() =>
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(Good, "en"));

        [Fact]
        public void RejectsWrongVersion() =>
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(Good.Replace("\"version\": 1", "\"version\": 2"), "de"));

        [Fact]
        public void RejectsMissingVersionOrEntries()
        {
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(@"{""language"":""de"",""entries"":{}}", "de"));
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(@"{""version"":1,""language"":""de""}", "de"));
        }

        [Theory]
        [InlineData("")]
        [InlineData("not json")]
        [InlineData("[]")]
        [InlineData("null")]
        public void RejectsInvalidJson(string json) =>
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(json, "de"));

        [Theory]
        [InlineData("../x.ogg")]
        [InlineData("dialog/../../x.ogg")]
        [InlineData("/abs.ogg")]
        [InlineData("C:/x.ogg")]
        [InlineData("a\\b.ogg")]
        [InlineData("")]
        public void SkipsUnsafePaths(string file)
        {
            string json = @"{""version"":1,""language"":""de"",""entries"":{""DT_X|A|K"":{""file"":""" + file.Replace("\\", "\\\\") + @""",""duration"":1}}}";
            var index = AudioIndex.Parse(json, "de");
            Assert.Equal(0, index.Count);
            Assert.Equal(1, index.Skipped);
        }

        [Fact]
        public void SkipsEntriesWithoutFileOrOfWrongShape()
        {
            string json = @"{""version"":1,""language"":""de"",""entries"":{
              ""A|B|1"": {""duration"": 1},
              ""A|B|2"": ""text"",
              ""A|B|3"": {""file"": 5, ""duration"": 1},
              ""A|B|4"": {""file"": ""dialog/ok.ogg""}
            }}";
            var index = AudioIndex.Parse(json, "de");
            Assert.Equal(1, index.Count);
            Assert.Equal(3, index.Skipped);
            Assert.True(index.TryGet("A|B|4", out var e));
            Assert.Equal(0.0, e.Duration);
        }

        [Fact]
        public void ResolvePathStaysInsideRoot()
        {
            string root = Path.Combine(Path.GetTempPath(), "audio-root");
            Assert.Equal(Path.Combine(root, "dialog", "a.ogg"), AudioIndex.ResolvePath(root, "dialog/a.ogg"));
            Assert.Null(AudioIndex.ResolvePath(root, "../a.ogg"));
        }

        [Theory]
        [InlineData("player/default/x.ogg", VoiceCategory.Player)]
        [InlineData("dialog/x.ogg", VoiceCategory.Dialog)]
        [InlineData("bark/x.ogg", VoiceCategory.Dialog)]
        public void CategoryComesFromFolder(string file, VoiceCategory expected) =>
            Assert.Equal(expected, AudioIndex.CategoryOf(file));
    }
}
```

(Ein UTF-8-BOM spielt keine Rolle: die Mod liest mit `File.ReadAllText`, das ein BOM entfernt.)

- [ ] **Step 2: Run to verify it fails**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter AudioIndexTests`
Expected: Build-Fehler (Typ `AudioIndex` fehlt).

- [ ] **Step 3: Write the implementation**

`mod/DrovaVoice.Core/AudioIndex.cs`:

```csharp
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace DrovaVoice.Core
{
    public enum VoiceCategory { Dialog, Player }

    public sealed record IndexEntry(string File, double Duration, VoiceCategory Category);

    public sealed class IndexFormatException : Exception
    {
        public IndexFormatException(string message) : base(message) { }
    }

    /// <summary>
    /// Liest Audio/&lt;Sprache&gt;/index.json (Vertrag: docs/audio-format.md). Die Mod bildet keine Dateinamen selbst,
    /// sie schlägt nur die volle Zeilen-ID nach. Kaputte Einträge werden übersprungen und gezählt, nicht gemeldet.
    /// </summary>
    public sealed class AudioIndex
    {
        public const int SupportedVersion = 1;
        private readonly Dictionary<string, IndexEntry> _entries;

        private AudioIndex(Dictionary<string, IndexEntry> entries, int skipped)
        {
            _entries = entries;
            Skipped = skipped;
        }

        public int Count => _entries.Count;
        public int Skipped { get; }

        public bool TryGet(string? id, out IndexEntry entry)
        {
            if (!string.IsNullOrEmpty(id) && _entries.TryGetValue(id!, out var found)) { entry = found; return true; }
            entry = null!;
            return false;
        }

        public static AudioIndex Parse(string json, string expectedLanguage)
        {
            JsonDocument doc;
            try { doc = JsonDocument.Parse(json); }
            catch (JsonException e) { throw new IndexFormatException("index.json ist kein gültiges JSON: " + e.Message); }
            using (doc)
            {
                var root = doc.RootElement;
                if (root.ValueKind != JsonValueKind.Object) throw new IndexFormatException("index.json: Wurzel ist kein Objekt");
                if (!root.TryGetProperty("version", out var version) || version.ValueKind != JsonValueKind.Number
                    || !version.TryGetInt32(out int v) || v != SupportedVersion)
                    throw new IndexFormatException($"index.json: Version fehlt oder ist nicht {SupportedVersion}");
                string? language = root.TryGetProperty("language", out var lang) && lang.ValueKind == JsonValueKind.String ? lang.GetString() : null;
                if (!string.Equals(language, expectedLanguage, StringComparison.OrdinalIgnoreCase))
                    throw new IndexFormatException($"index.json: Sprache '{language}' passt nicht zu '{expectedLanguage}'");
                if (!root.TryGetProperty("entries", out var entries) || entries.ValueKind != JsonValueKind.Object)
                    throw new IndexFormatException("index.json: 'entries' fehlt");

                var map = new Dictionary<string, IndexEntry>(StringComparer.Ordinal);
                int skipped = 0;
                foreach (var prop in entries.EnumerateObject())
                {
                    var value = prop.Value;
                    if (value.ValueKind != JsonValueKind.Object
                        || !value.TryGetProperty("file", out var fileEl) || fileEl.ValueKind != JsonValueKind.String)
                    { skipped++; continue; }
                    string file = fileEl.GetString() ?? "";
                    if (!IsSafeRelativePath(file)) { skipped++; continue; }
                    double duration = value.TryGetProperty("duration", out var d) && d.ValueKind == JsonValueKind.Number ? d.GetDouble() : 0.0;
                    map[prop.Name] = new IndexEntry(file, duration, CategoryOf(file));
                }
                return new AudioIndex(map, skipped);
            }
        }

        public static VoiceCategory CategoryOf(string file) =>
            file.StartsWith("player/", StringComparison.Ordinal) ? VoiceCategory.Player : VoiceCategory.Dialog;

        /// <summary>Relativ, mit '/', ohne '..', ohne Laufwerk, ohne Rückwärtsstrich.</summary>
        public static bool IsSafeRelativePath(string file)
        {
            if (string.IsNullOrEmpty(file)) return false;
            if (file.IndexOf('\\') >= 0 || file.IndexOf(':') >= 0 || file[0] == '/') return false;
            foreach (string part in file.Split('/'))
                if (part.Length == 0 || part == "." || part == "..") return false;
            return true;
        }

        public static string? ResolvePath(string root, string file) =>
            IsSafeRelativePath(file) ? Path.Combine(root, file.Replace('/', Path.DirectorySeparatorChar)) : null;
    }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter AudioIndexTests`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice.Core/AudioIndex.cs mod/DrovaVoice.Core.Tests/AudioIndexTests.cs
git commit -m "Add the audio index reader with path safety and categories"
```

---

### Task 2: Gain (Lautstärke mit Boost und Begrenzer)

**Files:**
- Create: `mod/DrovaVoice.Core/Gain.cs`
- Test: `mod/DrovaVoice.Core.Tests/GainTests.cs`

**Interfaces:**
- Produces: `Gain.MaxPercent` (=200), `Gain.ClampPercent(int) -> int`, `Gain.Factor(int percent) -> float`, `Gain.Limit(float) -> float`, `Gain.Apply(float[] samples, int percent)`.

- [ ] **Step 1: Write the failing tests**

`mod/DrovaVoice.Core.Tests/GainTests.cs`:

```csharp
using System;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class GainTests
    {
        [Fact]
        public void HundredPercentIsExactIdentity()
        {
            var samples = new[] { 0.9f, -0.95f, 0.123456f, 0f };
            var copy = (float[])samples.Clone();
            Gain.Apply(samples, 100);
            Assert.Equal(copy, samples);
        }

        [Fact]
        public void ZeroPercentIsSilence()
        {
            var samples = new[] { 0.5f, -0.9f };
            Gain.Apply(samples, 0);
            Assert.All(samples, s => Assert.Equal(0f, s));
        }

        [Fact]
        public void BelowHundredScalesLinearly()
        {
            var samples = new[] { 0.8f, -0.4f };
            Gain.Apply(samples, 50);
            Assert.Equal(0.4f, samples[0], 5);
            Assert.Equal(-0.2f, samples[1], 5);
        }

        [Fact]
        public void BoostBelowKneeIsLinear()
        {
            var samples = new[] { 0.3f, -0.3f };
            Gain.Apply(samples, 200);
            Assert.Equal(0.6f, samples[0], 5);
            Assert.Equal(-0.6f, samples[1], 5);
        }

        [Fact]
        public void BoostAboveKneeIsLimitedBelowOne()
        {
            var samples = new[] { 0.9f, -0.9f };
            Gain.Apply(samples, 200); // 1.8 vor dem Begrenzer
            Assert.InRange(samples[0], 0.8f, 1.0f);
            Assert.InRange(samples[1], -1.0f, -0.8f);
            Assert.Equal(-samples[0], samples[1], 6);
        }

        [Fact]
        public void BoostNeverExceedsFullScale()
        {
            var samples = new[] { 1f, -1f, 10f, -1000f, float.MaxValue / 4, 0.99f };
            Gain.Apply(samples, 200);
            Assert.All(samples, s => Assert.InRange(s, -1.0f, 1.0f));
        }

        [Fact]
        public void LimiterIsMonotonicAndContinuousAtKnee()
        {
            float prev = float.MinValue;
            for (float y = 0f; y <= 4f; y += 0.01f)
            {
                float o = Gain.Limit(y);
                Assert.True(o >= prev - 1e-6f, $"nicht monoton bei {y}");
                prev = o;
            }
            Assert.Equal(0.8f, Gain.Limit(0.8f), 6);
            Assert.Equal(0.8f, Gain.Limit(0.8001f), 3);
        }

        [Fact]
        public void LimiterMapsNaNToZero() =>
            Assert.Equal(0f, Gain.Limit(float.NaN));

        [Theory]
        [InlineData(-5, 0)]
        [InlineData(0, 0)]
        [InlineData(100, 100)]
        [InlineData(200, 200)]
        [InlineData(250, 200)]
        public void ClampsPercent(int input, int expected) =>
            Assert.Equal(expected, Gain.ClampPercent(input));

        [Fact]
        public void PercentOverMaxActsLikeMax()
        {
            var a = new[] { 0.5f, 0.9f };
            var b = (float[])a.Clone();
            Gain.Apply(a, 200);
            Gain.Apply(b, 999);
            Assert.Equal(a, b);
        }

        [Fact]
        public void EmptyArrayIsFine() => Gain.Apply(Array.Empty<float>(), 150);
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter GainTests`
Expected: Build-Fehler (`Gain` fehlt).

- [ ] **Step 3: Write the implementation**

`mod/DrovaVoice.Core/Gain.cs`:

```csharp
using System;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Lautstärke per Sample-Gain (AudioSource.volume endet bei 1,0). Bis einschließlich 100 % rein linear (100 % ist
    /// bit-genau unverändert); darüber begrenzt ein weicher Begrenzer ab dem Knie, damit nichts hart übersteuert.
    /// </summary>
    public static class Gain
    {
        public const int MaxPercent = 200;
        private const float Knee = 0.8f;

        public static int ClampPercent(int percent) => percent < 0 ? 0 : percent > MaxPercent ? MaxPercent : percent;

        public static float Factor(int percent) => ClampPercent(percent) / 100f;

        /// <summary>Weicher Begrenzer: bis zum Knie unverändert, darüber tanh-Kurve mit stetiger Steigung, Ausgabe höchstens ±1.</summary>
        public static float Limit(float y)
        {
            if (float.IsNaN(y)) return 0f;
            float a = Math.Abs(y);
            if (a <= Knee) return y;
            float o = Knee + (1f - Knee) * MathF.Tanh((a - Knee) / (1f - Knee));
            if (o > 1f) o = 1f;
            return y < 0f ? -o : o;
        }

        public static void Apply(float[] samples, int percent)
        {
            float f = Factor(percent);
            if (f == 1f) return;
            if (f < 1f)
            {
                for (int i = 0; i < samples.Length; i++) samples[i] *= f;
                return;
            }
            for (int i = 0; i < samples.Length; i++) samples[i] = Limit(samples[i] * f);
        }
    }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter GainTests`
Expected: alle PASS. (`float.MaxValue / 4 * 2` ist endlich; `Limit` liefert 1.)

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice.Core/Gain.cs mod/DrovaVoice.Core.Tests/GainTests.cs
git commit -m "Add the sample gain with a soft limiter above 100 percent"
```

---

### Task 3: ClipBudget (LRU nach Bytes)

**Files:**
- Create: `mod/DrovaVoice.Core/ClipBudget.cs`
- Test: `mod/DrovaVoice.Core.Tests/ClipBudgetTests.cs`

**Interfaces:**
- Produces: `new ClipBudget(long maxBytes, int protectedRecent)`; `Contains(string)`, `Touch(string)`, `Add(string key, long bytes) -> IReadOnlyList<string>` (verdrängte Schlüssel), `Remove(string)`, `TotalBytes`, `Count`.

- [ ] **Step 1: Write the failing tests**

`mod/DrovaVoice.Core.Tests/ClipBudgetTests.cs`:

```csharp
using System;
using System.Linq;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ClipBudgetTests
    {
        [Fact]
        public void NothingEvictedWithinBudget()
        {
            var b = new ClipBudget(100, 1);
            Assert.Empty(b.Add("a", 40));
            Assert.Empty(b.Add("b", 40));
            Assert.Equal(80, b.TotalBytes);
            Assert.Equal(2, b.Count);
        }

        [Fact]
        public void EvictsLeastRecentlyUsedFirst()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 40); b.Add("b", 40);
            var evicted = b.Add("c", 40);
            Assert.Equal(new[] { "a" }, evicted);
            Assert.False(b.Contains("a"));
            Assert.True(b.Contains("b") && b.Contains("c"));
            Assert.Equal(80, b.TotalBytes);
        }

        [Fact]
        public void TouchRefreshesRecency()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 40); b.Add("b", 40);
            b.Touch("a");
            Assert.Equal(new[] { "b" }, b.Add("c", 40));
        }

        [Fact]
        public void NewestEntriesAreNeverEvictedEvenOverBudget()
        {
            var b = new ClipBudget(50, 2);
            b.Add("a", 40); b.Add("b", 40);
            Assert.Equal(new[] { "a" }, b.Add("x", 0));   // nur 2 geschützt: a ist drittjüngster und wird verdrängt
            Assert.False(b.Contains("a"));
            Assert.True(b.Contains("b") && b.Contains("x"));
            Assert.Equal(40, b.TotalBytes);
        }

        [Fact]
        public void ProtectedEntriesStayWhenTheyAloneExceedTheBudget()
        {
            var b = new ClipBudget(10, 3);
            b.Add("a", 100); b.Add("b", 100); b.Add("c", 100);
            Assert.Equal(3, b.Count);
            Assert.Equal(300, b.TotalBytes);
        }

        [Fact]
        public void ReAddingUpdatesBytesAndRecency()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 30); b.Add("b", 30);
            Assert.Empty(b.Add("a", 50));
            Assert.Equal(80, b.TotalBytes);
            Assert.Equal(new[] { "b" }, b.Add("c", 30));
        }

        [Fact]
        public void RemoveFreesBytesAndIgnoresUnknownKeys()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 40);
            b.Remove("a");
            b.Remove("nope");
            Assert.Equal(0, b.TotalBytes);
            Assert.Equal(0, b.Count);
            Assert.False(b.Contains("a"));
        }

        [Fact]
        public void TouchOfUnknownKeyIsNoop()
        {
            var b = new ClipBudget(100, 1);
            b.Touch("nope");
            Assert.Equal(0, b.Count);
        }

        [Fact]
        public void RejectsNegativeBytes() =>
            Assert.Throws<ArgumentOutOfRangeException>(() => new ClipBudget(100, 1).Add("a", -1));

        [Fact]
        public void EvictsSeveralToFit()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 30); b.Add("b", 30); b.Add("c", 30);
            var evicted = b.Add("d", 90);
            Assert.Equal(new[] { "a", "b", "c" }, evicted.ToArray());
            Assert.Equal(90, b.TotalBytes);
        }
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter ClipBudgetTests`
Expected: Build-Fehler (`ClipBudget` fehlt).

- [ ] **Step 3: Write the implementation**

`mod/DrovaVoice.Core/ClipBudget.cs`:

```csharp
using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Buchführung für den Clip-Cache: zuletzt benutzte Einträge zuerst behalten, am wenigsten benutzte zuerst verdrängen,
    /// bis die Summe der Bytes im Budget liegt. Die jüngsten <c>protectedRecent</c> Einträge werden nie verdrängt (sie können
    /// gerade abgespielt werden), auch wenn sie allein das Budget überschreiten.
    /// </summary>
    public sealed class ClipBudget
    {
        private readonly long _maxBytes;
        private readonly int _protectedRecent;
        private readonly LinkedList<string> _order = new LinkedList<string>(); // vorn = jüngster
        private readonly Dictionary<string, (LinkedListNode<string> Node, long Bytes)> _items =
            new Dictionary<string, (LinkedListNode<string>, long)>(StringComparer.Ordinal);

        public ClipBudget(long maxBytes, int protectedRecent)
        {
            _maxBytes = maxBytes;
            _protectedRecent = protectedRecent < 1 ? 1 : protectedRecent;
        }

        public long TotalBytes { get; private set; }
        public int Count => _items.Count;

        public bool Contains(string key) => _items.ContainsKey(key);

        public void Touch(string key)
        {
            if (!_items.TryGetValue(key, out var item)) return;
            _order.Remove(item.Node);
            _order.AddFirst(item.Node);
        }

        /// <summary>Fügt ein oder aktualisiert einen Eintrag und liefert die verdrängten Schlüssel.</summary>
        public IReadOnlyList<string> Add(string key, long bytes)
        {
            if (bytes < 0) throw new ArgumentOutOfRangeException(nameof(bytes));
            Remove(key);
            var node = _order.AddFirst(key);
            _items[key] = (node, bytes);
            TotalBytes += bytes;

            var evicted = new List<string>();
            while (TotalBytes > _maxBytes && _order.Count > _protectedRecent)
            {
                var last = _order.Last!;
                _order.RemoveLast();
                var item = _items[last.Value];
                _items.Remove(last.Value);
                TotalBytes -= item.Bytes;
                evicted.Add(last.Value);
            }
            return evicted;
        }

        public void Remove(string key)
        {
            if (!_items.TryGetValue(key, out var item)) return;
            _order.Remove(item.Node);
            _items.Remove(key);
            TotalBytes -= item.Bytes;
        }
    }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter ClipBudgetTests`
Expected: alle PASS. Falls `NewestEntriesAreNeverEvictedEvenOverBudget` scheitert: `Add("x", 0)` ist der dritte Eintrag; Budget 50, Summe 80 > 50 und `_order.Count`=3 > 2, also wird `a` (Letzter) verdrängt, danach Summe 40 ≤ 50 — das Verhalten stimmt mit dem Test überein.

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice.Core/ClipBudget.cs mod/DrovaVoice.Core.Tests/ClipBudgetTests.cs
git commit -m "Add the LRU clip budget with protected recent entries"
```

---

### Task 4: VoiceSettings und OnceLog

**Files:**
- Create: `mod/DrovaVoice.Core/VoiceSettings.cs`, `mod/DrovaVoice.Core/OnceLog.cs`
- Test: `mod/DrovaVoice.Core.Tests/VoiceSettingsTests.cs`, `mod/DrovaVoice.Core.Tests/OnceLogTests.cs`

**Interfaces:**
- Consumes: `VoiceCategory` (Task 1), `Gain.MaxPercent` (Task 2).
- Produces:
  - `VoiceSettings.Create(bool enabled, int dialogPercent, int playerPercent, string? language, int cacheMegabytes, bool diagnostics, List<string> warnings) -> VoiceSettings`
  - Eigenschaften `Enabled`, `DialogPercent`, `PlayerPercent`, `Language`, `CacheMegabytes`, `Diagnostics`, `CacheBytes` (long); `PercentFor(VoiceCategory) -> int`
  - `new OnceLog(int cap = 10000)`, `OnceLog.ShouldLog(string key) -> bool`

- [ ] **Step 1: Write the failing tests**

`mod/DrovaVoice.Core.Tests/VoiceSettingsTests.cs`:

```csharp
using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class VoiceSettingsTests
    {
        [Fact]
        public void ValidValuesPassUnchangedWithoutWarnings()
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 120, 80, "de", 64, false, w);
            Assert.True(s.Enabled);
            Assert.Equal(120, s.DialogPercent);
            Assert.Equal(80, s.PlayerPercent);
            Assert.Equal("de", s.Language);
            Assert.Equal(64, s.CacheMegabytes);
            Assert.Equal(64L * 1024 * 1024, s.CacheBytes);
            Assert.False(s.Diagnostics);
            Assert.Empty(w);
        }

        [Theory]
        [InlineData(-1, 0)]
        [InlineData(250, 200)]
        public void VolumeIsClampedWithWarning(int input, int expected)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, input, input, "de", 64, false, w);
            Assert.Equal(expected, s.DialogPercent);
            Assert.Equal(expected, s.PlayerPercent);
            Assert.Equal(2, w.Count);
            Assert.Contains("DialogVolume", w[0]);
            Assert.Contains("PlayerVolume", w[1]);
        }

        [Theory]
        [InlineData(0, 8)]
        [InlineData(7, 8)]
        [InlineData(100000, 512)]
        public void CacheIsClamped(int input, int expected)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, "de", input, false, w);
            Assert.Equal(expected, s.CacheMegabytes);
            Assert.Single(w);
            Assert.Contains("CacheMB", w[0]);
        }

        [Theory]
        [InlineData(null)]
        [InlineData("")]
        [InlineData("   ")]
        [InlineData("../de")]
        [InlineData("de/en")]
        [InlineData("d e")]
        [InlineData("averyveryverylonglanguage")]
        public void BadLanguageFallsBackToDe(string? input)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, input, 64, false, w);
            Assert.Equal("de", s.Language);
            Assert.Single(w);
            Assert.Contains("AudioLanguage", w[0]);
        }

        [Fact]
        public void LanguageIsTrimmed()
        {
            var s = VoiceSettings.Create(true, 100, 100, " en-GB ", 64, false, new List<string>());
            Assert.Equal("en-GB", s.Language);
        }

        [Fact]
        public void PercentForUsesCategory()
        {
            var s = VoiceSettings.Create(true, 150, 60, "de", 64, true, new List<string>());
            Assert.Equal(150, s.PercentFor(VoiceCategory.Dialog));
            Assert.Equal(60, s.PercentFor(VoiceCategory.Player));
            Assert.True(s.Diagnostics);
        }
    }
}
```

`mod/DrovaVoice.Core.Tests/OnceLogTests.cs`:

```csharp
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class OnceLogTests
    {
        [Fact]
        public void LogsEachKeyOnce()
        {
            var log = new OnceLog();
            Assert.True(log.ShouldLog("a"));
            Assert.False(log.ShouldLog("a"));
            Assert.True(log.ShouldLog("b"));
        }

        [Fact]
        public void StopsLoggingNewKeysAtTheCap()
        {
            var log = new OnceLog(2);
            Assert.True(log.ShouldLog("a"));
            Assert.True(log.ShouldLog("b"));
            Assert.False(log.ShouldLog("c"));
            Assert.False(log.ShouldLog("a"));
        }
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter "VoiceSettingsTests|OnceLogTests"`
Expected: Build-Fehler.

- [ ] **Step 3: Write the implementation**

`mod/DrovaVoice.Core/VoiceSettings.cs`:

```csharp
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>Validierte Einstellungen aus MelonPreferences. Ungültige Werte werden begrenzt und als Warnung zurückgemeldet.</summary>
    public sealed class VoiceSettings
    {
        public const int MinCacheMegabytes = 8;
        public const int MaxCacheMegabytes = 512;
        public const string DefaultLanguage = "de";
        private const int MaxLanguageLength = 16;

        private VoiceSettings() { }

        public bool Enabled { get; private set; }
        public int DialogPercent { get; private set; }
        public int PlayerPercent { get; private set; }
        public string Language { get; private set; } = DefaultLanguage;
        public int CacheMegabytes { get; private set; }
        public bool Diagnostics { get; private set; }
        public long CacheBytes => CacheMegabytes * 1024L * 1024L;

        public int PercentFor(VoiceCategory category) => category == VoiceCategory.Player ? PlayerPercent : DialogPercent;

        public static VoiceSettings Create(bool enabled, int dialogPercent, int playerPercent, string? language,
                                           int cacheMegabytes, bool diagnostics, List<string> warnings)
        {
            return new VoiceSettings
            {
                Enabled = enabled,
                DialogPercent = ClampPercent("DialogVolume", dialogPercent, warnings),
                PlayerPercent = ClampPercent("PlayerVolume", playerPercent, warnings),
                Language = CleanLanguage(language, warnings),
                CacheMegabytes = ClampCache(cacheMegabytes, warnings),
                Diagnostics = diagnostics,
            };
        }

        private static int ClampPercent(string name, int value, List<string> warnings)
        {
            int clamped = Gain.ClampPercent(value);
            if (clamped != value) warnings.Add($"{name} = {value} liegt außerhalb 0–{Gain.MaxPercent}; verwende {clamped}.");
            return clamped;
        }

        private static int ClampCache(int value, List<string> warnings)
        {
            int clamped = value < MinCacheMegabytes ? MinCacheMegabytes : value > MaxCacheMegabytes ? MaxCacheMegabytes : value;
            if (clamped != value) warnings.Add($"CacheMB = {value} liegt außerhalb {MinCacheMegabytes}–{MaxCacheMegabytes}; verwende {clamped}.");
            return clamped;
        }

        private static string CleanLanguage(string? language, List<string> warnings)
        {
            string value = (language ?? "").Trim();
            if (value.Length > 0 && value.Length <= MaxLanguageLength && IsFolderSafe(value)) return value;
            warnings.Add($"AudioLanguage = '{language}' ist kein gültiger Ordnername; verwende '{DefaultLanguage}'.");
            return DefaultLanguage;
        }

        private static bool IsFolderSafe(string value)
        {
            foreach (char c in value)
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
            return true;
        }
    }
}
```

`mod/DrovaVoice.Core/OnceLog.cs`:

```csharp
using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>Entscheidet, ob ein Schlüssel (z. B. eine Zeilen-ID) schon geloggt wurde. Ab der Obergrenze werden keine neuen Schlüssel mehr gemeldet.</summary>
    public sealed class OnceLog
    {
        private readonly HashSet<string> _seen = new HashSet<string>(StringComparer.Ordinal);
        private readonly int _cap;

        public OnceLog(int cap = 10000) { _cap = cap; }

        public bool ShouldLog(string key)
        {
            if (_seen.Contains(key)) return false;
            if (_seen.Count >= _cap) return false;
            _seen.Add(key);
            return true;
        }
    }
}
```

(`char.IsAsciiLetterOrDigit` gibt es erst ab .NET 7; Core zielt auf net6.0, deshalb die Zeichenbereiche von Hand.)

- [ ] **Step 4: Run to verify it passes**

Run: `dotnet test mod/DrovaVoice.Core.Tests`
Expected: alle Core-Tests PASS (auch die bisherigen).

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice.Core/VoiceSettings.cs mod/DrovaVoice.Core/OnceLog.cs mod/DrovaVoice.Core.Tests/VoiceSettingsTests.cs mod/DrovaVoice.Core.Tests/OnceLogTests.cs
git commit -m "Add validated voice settings and the log-once helper"
```

---

### Task 5: OggDecoder (NVorbis) mit Smoke-Test im Scratchpad

**Files:**
- Modify: `mod/DrovaVoice/DrovaVoice.csproj` (NVorbis-Referenz)
- Create: `mod/DrovaVoice/Playback/OggDecoder.cs`
- Scratchpad (nicht im Repo): `<scratchpad>/oggsmoke/` Konsole, die `OggDecoder.cs` einbindet

**Interfaces:**
- Produces: `static class OggDecoder { static bool TryDecode(string path, out float[] samples, out int channels, out int sampleRate, out string? error) }` im Namespace `DrovaVoice.Playback`; ohne Il2Cpp-Abhängigkeit.

- [ ] **Step 1: Add the NVorbis reference**

In `mod/DrovaVoice/DrovaVoice.csproj` im `ItemGroup` mit den `Reference`-Elementen ergänzen:

```xml
    <Reference Include="NVorbis">
      <HintPath>$(DrovaGameDir)\UserLibs\NVorbis.dll</HintPath>
      <Private>false</Private>
    </Reference>
```

- [ ] **Step 2: Write the decoder**

`mod/DrovaVoice/Playback/OggDecoder.cs`:

```csharp
using System;
using System.IO;
using NVorbis;

namespace DrovaVoice.Playback
{
    /// <summary>OGG Vorbis -> float-Samples (verschachtelt bei mehreren Kanälen). Wirft nie; Fehler kommen als Text zurück.</summary>
    public static class OggDecoder
    {
        private const long MaxSamples = 48000L * 60 * 2; // 60 s Stereo bei 48 kHz: Schutz gegen absurd große Dateien

        public static bool TryDecode(string path, out float[] samples, out int channels, out int sampleRate, out string? error)
        {
            samples = Array.Empty<float>();
            channels = 0;
            sampleRate = 0;
            error = null;
            try
            {
                if (!File.Exists(path)) { error = "Datei fehlt"; return false; }
                using var reader = new VorbisReader(path);
                channels = reader.Channels;
                sampleRate = reader.SampleRate;
                long total = reader.TotalSamples * channels;
                if (channels < 1 || sampleRate < 1 || total < 1) { error = "leere oder ungültige Datei"; return false; }
                if (total > MaxSamples) { error = $"Datei zu lang ({total} Samples)"; return false; }
                var buffer = new float[total];
                int read = 0;
                while (read < buffer.Length)
                {
                    int n = reader.ReadSamples(buffer, read, buffer.Length - read);
                    if (n <= 0) break;
                    read += n;
                }
                if (read < 1) { error = "keine Samples lesbar"; return false; }
                if (read < buffer.Length) Array.Resize(ref buffer, read);
                samples = buffer;
                return true;
            }
            catch (Exception e)
            {
                error = e.GetType().Name + ": " + e.Message;
                samples = Array.Empty<float>();
                return false;
            }
        }
    }
}
```

- [ ] **Step 3: Smoke-test against real and broken files (Scratchpad)**

Im Scratchpad ein Konsolenprojekt `oggsmoke` anlegen, das `mod/DrovaVoice/Playback/OggDecoder.cs` per `<Compile Include=...>` einbindet und `NVorbis.dll` aus dem Spielordner per `HintPath` referenziert; es liest (a) die erste Datei unter `Mods/DrovaVoice/Audio/de/dialog/`, (b) eine abgeschnittene Kopie davon (erste 100 Bytes), (c) eine leere Datei, (d) eine nicht existierende Datei, (e) eine Textdatei mit Endung `.ogg`, und druckt `ok/ Fehlertext`, Kanäle, Samplerate, Anzahl Samples, größten Betrag.

Run: `dotnet run --project <scratchpad>/oggsmoke`
Expected: (a) `ok`, 1 Kanal, 48000 Hz, Samples > 0, Peak ≤ 1,0; (b)–(e) `false` mit Fehlertext, **keine Ausnahme**.

- [ ] **Step 4: Build the mod**

Run: `dotnet build mod/DrovaVoice -c Release`
Expected: `0 Fehler`. (Das Deploy-Ziel kopiert in den Spielordner; das Spiel muss geschlossen sein. Lässt sich die DLL nicht kopieren, Spiel beenden und wiederholen.)

- [ ] **Step 5: Commit**

```bash
git add mod/DrovaVoice/DrovaVoice.csproj mod/DrovaVoice/Playback/OggDecoder.cs
git commit -m "Add the Ogg decoder for the playback layer"
```

---

### Task 6: ClipStore und ClipLoader (AudioClip erzeugen, verdrängen)

**Files:**
- Create: `mod/DrovaVoice/Playback/ClipStore.cs`, `mod/DrovaVoice/Playback/ClipLoader.cs`

**Interfaces:**
- Consumes: `ClipBudget` (Task 3), `Gain.Apply` (Task 2), `AudioIndex.ResolvePath`, `IndexEntry` (Task 1), `OggDecoder.TryDecode` (Task 5).
- Produces:
  - `ClipStore(long maxBytes, int protectedRecent = 8)`; `bool TryGet(string id, out AudioClip clip)`; `void Put(string id, AudioClip clip, long bytes)`
  - `ClipLoader(string audioRoot)`; `AudioClip? Load(string id, IndexEntry entry, int percent, out long bytes, out string? error)`

Diese Schicht braucht UnityEngine und ist im Spiel prüfbar (Task 10). Hier: kompilieren.

- [ ] **Step 1: Write ClipStore**

`mod/DrovaVoice/Playback/ClipStore.cs`:

```csharp
using System.Collections.Generic;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Hält die geladenen Clips innerhalb des Budgets. Verdrängte Clips werden zerstört; das Spiel sieht danach
    /// <c>statement.audio == null</c> und die API ruft beim nächsten Ausführen der Zeile erneut den Connector.
    /// </summary>
    internal sealed class ClipStore
    {
        private readonly ClipBudget _budget;
        private readonly Dictionary<string, AudioClip> _clips = new Dictionary<string, AudioClip>();

        public ClipStore(long maxBytes, int protectedRecent = 8)
        {
            _budget = new ClipBudget(maxBytes, protectedRecent);
        }

        public int Count => _clips.Count;
        public long TotalBytes => _budget.TotalBytes;

        public bool TryGet(string id, out AudioClip clip)
        {
            if (_clips.TryGetValue(id, out var found))
            {
                if (found != null) { _budget.Touch(id); clip = found; return true; }
                _clips.Remove(id);       // vom Spiel zerstört (z. B. Szenenwechsel): vergessen
                _budget.Remove(id);
            }
            clip = null!;
            return false;
        }

        public void Put(string id, AudioClip clip, long bytes)
        {
            _clips[id] = clip;
            foreach (string evictedId in _budget.Add(id, bytes))
            {
                if (_clips.Remove(evictedId, out var old) && old != null) Object.Destroy(old);
            }
        }
    }
}
```

- [ ] **Step 2: Write ClipLoader**

`mod/DrovaVoice/Playback/ClipLoader.cs`:

```csharp
using System.Diagnostics;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>Datei -> Samples -> Gain -> AudioClip. Läuft synchron auf dem Hauptthread; über 500 ms bleibt die Zeile stumm.</summary>
    internal sealed class ClipLoader
    {
        public const int MaxDecodeMilliseconds = 500;
        private readonly string _audioRoot;

        public ClipLoader(string audioRoot) { _audioRoot = audioRoot; }

        public AudioClip? Load(string id, IndexEntry entry, int percent, out long bytes, out string? error)
        {
            bytes = 0;
            string? path = AudioIndex.ResolvePath(_audioRoot, entry.File);
            if (path == null) { error = "unsicherer Pfad"; return null; }
            var watch = Stopwatch.StartNew();
            if (!OggDecoder.TryDecode(path, out float[] samples, out int channels, out int sampleRate, out error)) return null;
            Gain.Apply(samples, percent);
            int frames = samples.Length / channels;
            var clip = AudioClip.Create("DrovaVoice/" + entry.File, frames, channels, sampleRate, false);
            if (clip == null || !clip.SetData(samples, 0)) { error = "AudioClip konnte nicht erzeugt werden"; return null; }
            watch.Stop();
            if (watch.ElapsedMilliseconds > MaxDecodeMilliseconds)
            {
                Object.Destroy(clip);
                error = $"Dekodieren dauerte {watch.ElapsedMilliseconds} ms (Grenze {MaxDecodeMilliseconds} ms)";
                return null;
            }
            bytes = (long)samples.Length * sizeof(float);
            error = null;
            return clip;
        }
    }
}
```

(`clip.SetData(float[], int)`: Die Il2Cpp-Interop-Assemblies nehmen `Il2CppStructArray<float>`; die implizite Umwandlung von `float[]` existiert, wie die API selbst sie benutzt. Meldet der Compiler dennoch einen Typfehler, `using Il2CppInterop.Runtime.InteropTypes.Arrays;` ergänzen und `new Il2CppStructArray<float>(samples)` übergeben.)

- [ ] **Step 3: Build**

Run: `dotnet build mod/DrovaVoice -c Release`
Expected: `0 Fehler`.

- [ ] **Step 4: Commit**

```bash
git add mod/DrovaVoice/Playback/ClipStore.cs mod/DrovaVoice/Playback/ClipLoader.cs
git commit -m "Add the clip store and loader for the playback layer"
```

---

### Task 7: VoiceService (Lookup, Cache, Laden, Logging)

**Files:**
- Create: `mod/DrovaVoice/Playback/VoiceService.cs`

**Interfaces:**
- Consumes: `AudioIndex`, `IndexEntry`, `VoiceSettings`, `OnceLog`, `ClipStore`, `ClipLoader`.
- Produces: `VoiceService(AudioIndex index, string audioRoot, VoiceSettings settings, MelonLogger.Instance log)`; `AudioClip? GetClip(string? id)` (`null` = stumm); `void LogError(string where, Exception e)`.

- [ ] **Step 1: Write the service**

`mod/DrovaVoice/Playback/VoiceService.cs`:

```csharp
using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>Zentrale Stelle der Wiedergabe: ID -> Index -> Cache oder Laden. Fehlschläge werden gemerkt und nur einmal geloggt.</summary>
    internal sealed class VoiceService
    {
        private readonly AudioIndex _index;
        private readonly VoiceSettings _settings;
        private readonly ClipStore _store;
        private readonly ClipLoader _loader;
        private readonly MelonLogger.Instance _log;
        private readonly HashSet<string> _failed = new HashSet<string>(StringComparer.Ordinal);
        private readonly OnceLog _onceLog = new OnceLog();
        private int _hits, _misses;

        public VoiceService(AudioIndex index, string audioRoot, VoiceSettings settings, MelonLogger.Instance log)
        {
            _index = index;
            _settings = settings;
            _log = log;
            _store = new ClipStore(settings.CacheBytes);
            _loader = new ClipLoader(audioRoot);
        }

        public AudioClip? GetClip(string? id)
        {
            if (string.IsNullOrEmpty(id)) return null;
            if (!_index.TryGet(id, out var entry))
            {
                _misses++;
                if (_settings.Diagnostics && _onceLog.ShouldLog("miss|" + id)) _log.Msg($"[Zeile] ohne Eintrag: {id}");
                return null;
            }
            if (_store.TryGet(id!, out var cached)) return cached;
            if (_failed.Contains(id!)) return null;

            var clip = _loader.Load(id!, entry, _settings.PercentFor(entry.Category), out long bytes, out string? error);
            if (clip == null)
            {
                _failed.Add(id!);
                if (_onceLog.ShouldLog("fail|" + id)) _log.Warning($"Zeile bleibt stumm ({error}): {id}");
                return null;
            }
            _store.Put(id!, clip, bytes);
            _hits++;
            if (_settings.Diagnostics && _onceLog.ShouldLog("hit|" + id))
                _log.Msg($"[Zeile] geladen: {id} ({entry.File}, {entry.Duration:0.00} s, {entry.Category}); Cache {_store.Count} Clips, {_store.TotalBytes / 1024 / 1024} MB");
            return clip;
        }

        public void LogError(string where, Exception e)
        {
            if (_onceLog.ShouldLog("err|" + where + "|" + e.GetType().Name))
                _log.Error($"{where}: {e.GetType().Name}: {e.Message}");
        }
    }
}
```

- [ ] **Step 2: Build**

Run: `dotnet build mod/DrovaVoice -c Release`
Expected: `0 Fehler`.

- [ ] **Step 3: Commit**

```bash
git add mod/DrovaVoice/Playback/VoiceService.cs
git commit -m "Add the voice service: index lookup, cache and silent failure"
```

---

### Task 8: VoiceConnector, ChoiceHook und Mod-Verkabelung

**Files:**
- Create: `mod/DrovaVoice/Playback/VoiceConnector.cs`, `mod/DrovaVoice/Playback/ChoiceHook.cs`
- Modify: `mod/DrovaVoice/DrovaVoiceMod.cs` (Einstellungen, Service, verzögerter Ersatz)

**Interfaces:**
- Consumes: `VoiceService.GetClip`, `LineIds.Statement/Choice`, `AudioManager.ReplaceDialogueAudioConnector`, `IAudioConnector`.
- Produces: `VoiceConnector(VoiceService)`, `ChoiceHook.Service` (statisches Feld, `null` = aus).

- [ ] **Step 1: Write the connector**

`mod/DrovaVoice/Playback/VoiceConnector.cs`:

```csharp
using System;
using DrovaVoice.Core;
using Drova_Modding_API.Systems.Audio;
using Il2CppNodeCanvas.DialogueTrees;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Ersetzt den Standardconnector der Modding API. Beim Laden eines Baums passiert nichts (kein Vorladen);
    /// der API-Patch ruft OnWorldDialogueStatement bei jeder Aussage, deren audio noch null ist.
    /// </summary>
    internal sealed class VoiceConnector : IAudioConnector
    {
        private readonly VoiceService _service;

        public VoiceConnector(VoiceService service) { _service = service; }

        public void OnDialogueTreeLoaded(DialogueTree dialogueTree) { }

        public void OnWorldDialogueStatement(DS_StatementNode statementNode)
        {
            try
            {
                var statement = statementNode.statement;
                var tree = statementNode.DLGTree;
                string locaPath = statement.useGlobalLoca ? statement.GlobalLocaPath : tree.LocaPath;
                string id = LineIds.Statement(tree.name, locaPath, statement.locaKey);
                var clip = _service.GetClip(id);
                if (clip != null) statement.audio = clip;
            }
            catch (Exception e) { _service.LogError("OnWorldDialogueStatement", e); }
        }
    }
}
```

- [ ] **Step 2: Write the choice hook**

`mod/DrovaVoice/Playback/ChoiceHook.cs`:

```csharp
using System;
using DrovaVoice.Core;
using HarmonyLib;
using Il2CppNodeCanvas.DialogueTrees;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Die API spielt eine gewählte Option nur mit Ton, wenn choice.statement.audio schon gesetzt ist; ihr eigener Handler
    /// für Auswahlknoten ist leer. Deshalb laden wir die Clips aller Optionen, bevor der Knoten ausgeführt (angezeigt) wird.
    /// </summary>
    [HarmonyPatch(typeof(DS_MultipleChoiceNode), "OnExecute")]
    internal static class ChoiceHook
    {
        /// <summary>null = Vertonung aus; der Prefix tut dann nichts.</summary>
        public static VoiceService? Service;

        private static void Prefix(DS_MultipleChoiceNode __instance)
        {
            var service = Service;
            if (service == null) return;
            try
            {
                var tree = __instance.DLGTree;
                var choices = __instance.availableChoices;
                for (int k = 0; k < choices.Count; k++)
                {
                    try   // je Option: ein Fehler (z. B. leerer Schlüssel) lässt die übrigen Optionen nicht aus
                    {
                        var statement = choices[k].statement;
                        if (statement.audio != null) continue;
                        string locaPath = statement.useGlobalLoca ? statement.GlobalLocaPath : tree.LocaPath;
                        string id = LineIds.Choice(tree.name, locaPath, statement.locaKey, k);
                        var clip = service.GetClip(id);
                        if (clip != null) statement.audio = clip;
                    }
                    catch (Exception e) { service.LogError("ChoiceHook", e); }
                }
            }
            catch (Exception e) { service.LogError("ChoiceHook", e); }
        }
    }
}
```

- [ ] **Step 3: Wire the mod**

`mod/DrovaVoice/DrovaVoiceMod.cs` ändern:

1. `using`s ergänzen: `using System.Linq;` nicht nötig; ergänzen `using Drova_Modding_API.Systems.Audio;`, `using Drova_Modding_API.Systems.WorldEvents;`, `using DrovaVoice.Playback;`.
2. Felder ergänzen:

```csharp
        private VoiceService? _voice;
        private bool _connectorInstalled;
        private bool _connectorFailed;
        private string AudioRoot(string language) => Path.Combine(ModDir, "Audio", language);
```

3. `OnInitializeMelon` ersetzen durch (die `ExportLanguage`-Zeile bleibt inhaltlich, die Kategorie wird in einer lokalen Variable gehalten):

```csharp
        public override void OnInitializeMelon()
        {
            var category = MelonPreferences.CreateCategory("DrovaVoice");
            _language = category.CreateEntry("ExportLanguage", "de", description: "Sprache des Exports (Ordnername)");
            var enabled = category.CreateEntry("Enabled", true, description: "Vertonung an/aus");
            var dialogVolume = category.CreateEntry("DialogVolume", 100, description: "Lautstärke NPC-Stimmen in Prozent (0-200, über 100 = Verstärkung)");
            var playerVolume = category.CreateEntry("PlayerVolume", 100, description: "Lautstärke Spielerzeilen in Prozent (0-200, über 100 = Verstärkung)");
            var audioLanguage = category.CreateEntry("AudioLanguage", "de", description: "Unterordner unter Mods/DrovaVoice/Audio");
            var cacheMb = category.CreateEntry("CacheMB", 64, description: "Obergrenze für geladene Clips in MB (8-512)");
            var diagnostics = category.CreateEntry("Diagnostics", false, description: "Jede Zeile einmal loggen (geladen/ohne Eintrag)");
            Directory.CreateDirectory(ModDir);
            string probe = LineIds.AudioFileName(LineIds.Statement("DT_Main_NPC_Adela", "Dialog/NPC_Adela", "Plh_5"));
            LoggerInstance.Msg($"DrovaVoice {Info.Version} geladen (Core ok: {probe}). Export: Datei export.trigger in {ModDir} anlegen oder F9 drücken.");

            var warnings = new List<string>();
            var settings = VoiceSettings.Create(enabled.Value, dialogVolume.Value, playerVolume.Value, audioLanguage.Value, cacheMb.Value, diagnostics.Value, warnings);
            foreach (string w in warnings) LoggerInstance.Warning(w);
            _voice = CreateVoice(settings);
            ChoiceHook.Service = _voice;
        }

        private VoiceService? CreateVoice(VoiceSettings settings)
        {
            if (!settings.Enabled) { LoggerInstance.Msg("Vertonung ist ausgeschaltet (Enabled=false)."); return null; }
            string root = AudioRoot(settings.Language);
            string indexPath = Path.Combine(root, "index.json");
            try
            {
                if (!File.Exists(indexPath)) { LoggerInstance.Warning($"Kein index.json unter {indexPath}; Vertonung bleibt aus."); return null; }
                var index = AudioIndex.Parse(File.ReadAllText(indexPath), settings.Language);
                LoggerInstance.Msg($"Index: {index.Count} Zeilen ({index.Skipped} übersprungen), Dialog {settings.DialogPercent} %, Spieler {settings.PlayerPercent} %, Cache {settings.CacheMegabytes} MB.");
                return new VoiceService(index, root, settings, LoggerInstance);
            }
            catch (Exception e)
            {
                LoggerInstance.Error($"Index nicht nutzbar, Vertonung bleibt aus: {e.GetType().Name}: {e.Message}");
                return null;
            }
        }

        /// <summary>
        /// AudioManager der API legt in seinem statischen Konstruktor einen Provider an, der WorldEventSystemManager.Instance braucht;
        /// im Hauptmenü ist die noch null, und ein fehlgeschlagener statischer Konstruktor bleibt dauerhaft kaputt.
        /// Deshalb wird der Connector erst ersetzt, wenn die Instanz existiert.
        /// </summary>
        private void TryInstallConnector()
        {
            if (_voice == null || _connectorInstalled || _connectorFailed) return;
            if (WorldEventSystemManager.Instance == null) return;
            try
            {
                AudioManager.ReplaceDialogueAudioConnector(new VoiceConnector(_voice));
                _connectorInstalled = true;
                LoggerInstance.Msg("Audio-Connector der Modding API ersetzt.");
            }
            catch (Exception e)
            {
                _connectorFailed = true;
                LoggerInstance.Error($"Connector konnte nicht ersetzt werden, Vertonung bleibt aus: {e.GetType().Name}: {e.Message}");
            }
        }
```

4. In `OnUpdate` direkt nach `_frame++;` einfügen:

```csharp
            if (_frame % 60 == 15) TryInstallConnector();
```

- [ ] **Step 4: Build**

Run: `dotnet build mod/DrovaVoice -c Release`
Expected: `0 Fehler`. Typische Anpassungen, falls der Compiler meckert: Namespace von `DS_StatementNode`/`DS_MultipleChoiceNode` ist `Il2CppNodeCanvas.DialogueTrees` (wie im Exporter); `DLGTree` liefert `DialogueTree`; fehlt `HarmonyLib`, in der `.csproj` `0Harmony` aus `$(DrovaGameDir)\MelonLoader\net6\0Harmony.dll` (`Private=false`) referenzieren.

- [ ] **Step 5: Run the Core tests once more and commit**

Run: `dotnet test mod/DrovaVoice.Core.Tests`
Expected: alle PASS.

```bash
git add mod/DrovaVoice/Playback/VoiceConnector.cs mod/DrovaVoice/Playback/ChoiceHook.cs mod/DrovaVoice/DrovaVoiceMod.cs mod/DrovaVoice/DrovaVoice.csproj
git commit -m "Wire the playback layer: connector, choice hook, settings and delayed install"
```

---

### Task 9: Doku und Spec nachtragen

**Files:**
- Create: `docs/playback.md`
- Modify: `docs/superpowers/specs/2026-10-14-plan-4-wiedergabe-design.md` (Einstellungstabelle, §9, Befund zum Zeitpunkt des Ersetzens), `docs/audio-format.md` (Verweis auf `docs/playback.md`)

- [ ] **Step 1: Write `docs/playback.md`**

Inhalt (auf Deutsch, ohne Spieltexte):

- Überblick: wie die Wiedergabe funktioniert (Ablauf einer Zeile, §4 der Spec in Kurzform).
- Einstellungen: Tabelle aus Spec §6 plus `Diagnostics`; Ort der Datei: `<Spiel>/UserData/MelonPreferences.cfg`, Kategorie `[DrovaVoice]`; Änderungen gelten nach Neustart des Spiels.
- Fehlersuche: Log-Zeilen und was sie bedeuten (`Index: N Zeilen`, `Audio-Connector der Modding API ersetzt.`, `Zeile bleibt stumm (…)`, `[Zeile] ohne Eintrag`, `[Zeile] geladen`).
- Abnahme-Checkliste (Task 10).
- Bekannte Grenzen: keine Namensvarianten, keine Barks/Briefe, keine Regler im Spiel.

- [ ] **Step 2: Update the spec**

In der Einstellungstabelle `Diagnostics` (`false`, Bedeutung „jede Zeile einmal loggen“) ergänzen. In §9 Risiko P1 ersetzen durch: „`AudioManager`s statischer Konstruktor scheitert im Hauptmenü, weil `WorldEventSystemManager.Instance` noch `null` ist; deshalb Ersetzen erst in `OnUpdate`, wenn die Instanz existiert (umgesetzt)“. In §2 als Befund 8 ergänzen.

- [ ] **Step 3: Commit**

```bash
git add docs/playback.md docs/superpowers/specs/2026-10-14-plan-4-wiedergabe-design.md docs/audio-format.md
git commit -m "Document the playback layer and the delayed connector install"
```

---

### Task 10: Abnahme im Spiel (mit dem Nutzer)

**Files:**
- Create: `docs/decisions/2026-10-playback-durchstich.md` (nach der Abnahme)

Diese Task braucht das Spiel und den Nutzer. Ablauf:

- [ ] **Step 1: Vorbereitung** — Spiel geschlossen, `dotnet build mod/DrovaVoice -c Release` deployt DLLs. In `UserData/MelonPreferences.cfg` (entsteht beim ersten Start) `Diagnostics = true` setzen, dann Spiel starten.

- [ ] **Step 2: Log nach dem Start prüfen** (`MelonLoader/Latest.log`): erwartet `Index: 255 Zeilen …`; **keine** `TypeInitializationException` im Hauptmenü; `Audio-Connector der Modding API ersetzt.` erscheint erst nach dem Laden eines Spielstands.

- [ ] **Step 3: Adela ansprechen** — erwartet: `[Zeile] geladen: DT_…` je Zeile (IDs passen zum Index, damit ist P3 geklärt), Stimme hörbar, Untertitel laufen synchron. Zeilen mit `$GVAR:` bleiben stumm.

- [ ] **Step 4: Spieleroptionen** — beim Erscheinen einer Auswahl `[Zeile] geladen … Player`-Meldungen; nach dem Wählen spricht der Spieler die Option (P4).

- [ ] **Step 5: Überspringen und Schließen (R5, P5)** — Zeile mit der Überspringen-Taste beenden, Dialogfenster mit Esc schließen: Stimme verstummt? Weiterlauf nach dem Clip ohne Hänger? Ergebnis notieren; verstummt sie nicht, ist das ein Folgeauftrag (`localSource.Stop()` am Handler).

- [ ] **Step 6: Jero (große Figur)** — durch ein längeres Gespräch gehen: keine Ruckler (Log `geladen`-Zeilen, Cache wächst höchstens bis 64 MB), keine Fehler.

- [ ] **Step 7: Regler** — `DialogVolume`/`PlayerVolume` ändern (z. B. 150 und 80), Spiel neu starten, hörbar anders; Wert 250 wird beim Start mit Warnung auf 200 begrenzt.

- [ ] **Step 8: Ergebnis festhalten und committen** — `docs/decisions/2026-10-playback-durchstich.md` (nur Zahlen/Entscheidungen, keine Spieltexte): Urteil des Nutzers, Antworten zu P1–P5/R5, Lautstärkeempfehlung, offene Punkte.

```bash
git add docs/decisions/2026-10-playback-durchstich.md
git commit -m "Record the in-game playback result for Adela and Jero"
```

---

## Self-Review (Plan gegen Spec)

- Spec §1 Umfang → Tasks 1–8; Nicht-Umfang bewusst nicht enthalten.
- §2 Befunde → Plan-Befund (8) und Task 8 (Connector `OnDialogueTreeLoaded` No-op, `OnWorldDialogueStatement`, Choice-Prefix auf `OnExecute`).
- §3 Architektur → Dateitabelle; `VoiceCategory` kommt aus dem Pfad (Task 1).
- §4 Ablauf, §7 Fehlerverhalten → Tasks 6–8 (500 ms, `_failed`, Einmal-Log, try/catch, Zerstören verdrängter Clips, Index-Fehler schalten ab).
- §5 Lautstärke → Task 2 (100 % exakt, Begrenzer, Clamp) und Task 6 (Gain beim Laden).
- §6 Einstellungen → Task 4 und Task 8 (`Diagnostics` zusätzlich, in Task 9 in der Spec nachgetragen).
- §8 Phasen: Phase 0 entfällt als eigener Mess-Build, weil `Diagnostics` die Messung in Task 10 liefert; Phase 1–4 = Tasks 1–9, Phase 5 = Task 10.
- Typ-Konsistenz: `IndexEntry(File, Duration, Category)`, `GetClip(string?)`, `ClipStore.Put(id, clip, bytes)`, `VoiceSettings.Create(..., List<string>)` stimmen in allen Tasks überein.

---

## Änderungen nach dem Review (2026-10-14)

Der lesende Opus-Review fand Abweichungen, die nach der Umsetzung der Tasks 1–9 behoben wurden; maßgeblich ist Spec §10, der Code ist die Wahrheit, die Code-Blöcke der Tasks 6–8 oben sind der Stand vor dem Review. Geändert: `ClipLoader.Load(entry, percent, out bytes, out elapsedMs, out error)` (kein Verwerfen bei 500 ms, Ausnahmen gefangen, Clip im Fehlerpfad zerstört), `VoiceService.GetChoiceClip/Diag/Problem/LogError(where, id, e)`, `VoiceConnector` und `ChoiceHook` mit `LineIds.TryStatement/TryChoice/ResolveLocaPath`, `ChoiceHook` nur bei `saySelection` und erst nach dem Ersatz des Connectors, `AudioIndex.TryGetUniqueChoice`, Installation in jedem Frame, Export-Warnung im Hauptmenü.
