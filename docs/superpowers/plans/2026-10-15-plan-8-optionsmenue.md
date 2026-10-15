# Plan 8: Regler im Optionsmenü Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vertonung an/aus, Dialog-, Spieler- und Bark-Lautstärke sowie Bark-Min/Max stellt der Nutzer im Optionsmenü des Spiels ein; Änderungen wirken ohne Neustart und bleiben gespeichert.

**Architecture:** Ein Core-Teil (`MenuValues`, `MenuKeys`, `VoiceSettings.WithOverrides`, `VoiceSettings.Diff`) bildet aus Datei-Einstellungen und Menüwerten einen neuen unveränderlichen Schnappschuss. Die Mod (`VoiceMenu`) hängt sich wie `Drova_Modding_API.Systems.ModdingUI.ModdingUI` an `OptionMenuAccess.OnOptionMenuOpen`/`OnOptionMenuClose`, baut mit `OptionUIBuilder` das Panel, liest die Werte über `ConfigAccessor` aus der Spielkonfiguration und tauscht den Schnappschuss im `VoiceService` aus. Der Clip-Cache wird nach Lautstärke geschlüsselt (`id@prozent`), sodass alte Clips von selbst aus dem Cache altern.

**Tech Stack:** C# net6 (MelonLoader, Il2Cpp-Interop, xUnit im Core), Mono.Cecil (Wegwerfwerkzeug im Scratchpad zum Lesen der API).

**Spec:** `docs/superpowers/specs/2026-10-15-optionsmenue-design.md` (dazu `docs/playback.md`, `docs/HANDOFF.md`).

## Global Constraints

- Antworten, Doku und Kommentare auf Deutsch; Commits englisch, Imperativ, **ohne** `Co-Authored-By`- oder sonstige Claude-Zeile.
- Nichts pushen oder mergen ohne Nachfrage. Arbeit auf Branch `plan-8-optionsmenue` (von `main`).
- Mod bauen (`dotnet build mod/DrovaVoice -c Release`) kopiert in den Spielordner: **Spiel muss geschlossen sein**.
- Ausnahmen in Spiel-Hooks immer abfangen (Haupt-Spec §10); scheitert das Panel, läuft die Mod mit den Datei-Einstellungen weiter.
- Grenzen wie bisher: Lautstärke 0 bis 200 %, `BarkMinDistance` ≥ 0 und `BarkMaxDistance` > Min, sonst Standard 15 bis 120 mit Warnung.
- Option-Schlüssel im Spielspeicher: `DrovaVoice_Enabled`, `DrovaVoice_DialogVolume`, `DrovaVoice_PlayerVolume`, `DrovaVoice_BarkVolume`, `DrovaVoice_BarkMinDistance`, `DrovaVoice_BarkMaxDistance` (Unterstriche statt Punkten, damit der Konfigurationsspeicher des Spiels keine Pfadtrenner sieht).
- Tests: `dotnet test mod/DrovaVoice.Core.Tests` muss vor jedem Commit grün sein (Stand: 192).

## Review Focus

- Ungültige oder fehlende Menüwerte (NaN, Max ≤ Min, 250 %, nicht lesbarer Konfigurationswert) dürfen weder abstürzen noch die Vertonung stumm schalten: Task 1 (Tests).
- Wird die Vertonung im Menü ausgeschaltet und später wieder angeschaltet, muss sie ohne Neustart zurückkommen, auch wenn sie beim Start aus war: Task 2.
- Lautstärke ändern darf keinen laufenden Clip zerstören (Cache nach Prozent geschlüsselt, kein `Clear`): Task 2.
- Panel-Bau zweimal (Menü mehrfach öffnen) darf keine doppelten Regler erzeugen; die API gibt für eine schon verwendete Panel-ID keinen neuen Builder zurück: Task 3.
- Ein Fehler beim Panel-Bau oder Lesen der Konfiguration lässt die Datei-Einstellungen gelten, einmal geloggt: Task 3.

---

### Task 0: Branch anlegen

- [ ] **Step 1: Branch und Ausgangslage**

```bash
cd /d/Games/Projekte/DrovaTTAI
git status --short && git switch -c plan-8-optionsmenue
dotnet test mod/DrovaVoice.Core.Tests 2>&1 | tail -1
```
Expected: sauberer Baum (außer evtl. nicht verfolgte Arbeitsdateien), `Bestanden! … erfolgreich: 192`.

---

### Task 1: Core: Menüwerte, Schnappschuss, Änderungserkennung

**Files:**
- Create: `mod/DrovaVoice.Core/MenuValues.cs`, `mod/DrovaVoice.Core.Tests/MenuValuesTests.cs`
- Modify: `mod/DrovaVoice.Core/VoiceSettings.cs`

**Interfaces:**
- Produces: `public sealed record MenuValues(bool? Enabled = null, int? DialogPercent = null, int? PlayerPercent = null, int? BarkPercent = null, float? BarkMinDistance = null, float? BarkMaxDistance = null)`; `public static class MenuKeys { Enabled, DialogVolume, PlayerVolume, BarkVolume, BarkMinDistance, BarkMaxDistance : const string }`; `[Flags] public enum SettingsChange { None = 0, Enabled = 1, Volume = 2, Range = 4 }`; `VoiceSettings.WithOverrides(MenuValues values, List<string> warnings) : VoiceSettings`; `static SettingsChange VoiceSettings.Diff(VoiceSettings oldSettings, VoiceSettings newSettings)`.
- Consumes: `VoiceSettings.Create(...)` (Grenzen wie bisher), `Gain.ClampPercent`.

- [ ] **Step 1: Failing Tests schreiben**

`mod/DrovaVoice.Core.Tests/MenuValuesTests.cs`:

```csharp
using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class MenuValuesTests
    {
        private static VoiceSettings Baseline(List<string>? w = null) =>
            VoiceSettings.Create(true, 100, 90, "de", 64, true, w ?? new List<string>(), 80, 15f, 120f);

        [Fact]
        public void MissingValuesKeepTheBaseline()
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(), w);
            Assert.True(s.Enabled);
            Assert.Equal(100, s.DialogPercent);
            Assert.Equal(90, s.PlayerPercent);
            Assert.Equal(80, s.BarkPercent);
            Assert.Equal(15f, s.BarkMinDistance);
            Assert.Equal(120f, s.BarkMaxDistance);
            Assert.Equal("de", s.Language);
            Assert.True(s.Diagnostics);
            Assert.Equal(64, s.CacheMegabytes);
            Assert.Empty(w);
        }

        [Fact]
        public void MenuValuesWinOverTheBaseline()
        {
            var s = Baseline().WithOverrides(new MenuValues(false, 150, 60, 200, 5f, 40f), new List<string>());
            Assert.False(s.Enabled);
            Assert.Equal(150, s.DialogPercent);
            Assert.Equal(60, s.PlayerPercent);
            Assert.Equal(200, s.BarkPercent);
            Assert.Equal(5f, s.BarkMinDistance);
            Assert.Equal(40f, s.BarkMaxDistance);
        }

        [Fact]
        public void VolumeIsClampedWithAWarning()
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(DialogPercent: 250, BarkPercent: -5), w);
            Assert.Equal(200, s.DialogPercent);
            Assert.Equal(0, s.BarkPercent);
            Assert.Contains(w, m => m.Contains("DialogVolume"));
            Assert.Contains(w, m => m.Contains("BarkVolume"));
        }

        [Theory]
        [InlineData(50f, 50f)]
        [InlineData(60f, 10f)]
        [InlineData(float.NaN, 40f)]
        public void InvalidRangeFallsBackToTheDefaults(float min, float max)
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(BarkMinDistance: min, BarkMaxDistance: max), w);
            Assert.Equal(VoiceSettings.DefaultBarkMinDistance, s.BarkMinDistance);
            Assert.Equal(VoiceSettings.DefaultBarkMaxDistance, s.BarkMaxDistance);
            Assert.NotEmpty(w);
        }

        [Fact]
        public void OnlyOneRangeValueKeepsTheOtherFromTheBaseline()
        {
            var s = Baseline().WithOverrides(new MenuValues(BarkMaxDistance: 200f), new List<string>());
            Assert.Equal(15f, s.BarkMinDistance);
            Assert.Equal(200f, s.BarkMaxDistance);
        }

        [Fact]
        public void DiffReportsEachKindOfChangeSeparately()
        {
            var a = Baseline();
            Assert.Equal(SettingsChange.None, VoiceSettings.Diff(a, Baseline()));
            Assert.Equal(SettingsChange.Enabled, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(Enabled: false), new List<string>())));
            Assert.Equal(SettingsChange.Volume, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(PlayerPercent: 70), new List<string>())));
            Assert.Equal(SettingsChange.Volume, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(BarkPercent: 120), new List<string>())));
            Assert.Equal(SettingsChange.Range, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(BarkMinDistance: 10f), new List<string>())));
            Assert.Equal(SettingsChange.Enabled | SettingsChange.Volume | SettingsChange.Range,
                VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(false, 10, null, null, 1f, 50f), new List<string>())));
        }

        [Fact]
        public void KeysAreDistinctAndPrefixed()
        {
            var keys = new[] { MenuKeys.Enabled, MenuKeys.DialogVolume, MenuKeys.PlayerVolume, MenuKeys.BarkVolume, MenuKeys.BarkMinDistance, MenuKeys.BarkMaxDistance };
            Assert.Equal(keys.Length, new HashSet<string>(keys).Count);
            Assert.All(keys, k => Assert.StartsWith("DrovaVoice_", k));
        }
    }
}
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `dotnet test mod/DrovaVoice.Core.Tests --filter MenuValuesTests 2>&1 | grep -c "error CS"`
Expected: > 0 (Kompilierfehler: `MenuValues`, `WithOverrides`, `Diff` fehlen).

- [ ] **Step 3: Implementieren**

`mod/DrovaVoice.Core/MenuValues.cs`:

```csharp
using System;

namespace DrovaVoice.Core
{
    /// <summary>Werte aus dem Optionsmenü; null = nicht gesetzt (Wert der Datei-Einstellungen bleibt).</summary>
    public sealed record MenuValues(bool? Enabled = null, int? DialogPercent = null, int? PlayerPercent = null,
                                    int? BarkPercent = null, float? BarkMinDistance = null, float? BarkMaxDistance = null);

    /// <summary>Schlüssel im Konfigurationsspeicher des Spiels (Optionsmenü).</summary>
    public static class MenuKeys
    {
        public const string Enabled = "DrovaVoice_Enabled";
        public const string DialogVolume = "DrovaVoice_DialogVolume";
        public const string PlayerVolume = "DrovaVoice_PlayerVolume";
        public const string BarkVolume = "DrovaVoice_BarkVolume";
        public const string BarkMinDistance = "DrovaVoice_BarkMinDistance";
        public const string BarkMaxDistance = "DrovaVoice_BarkMaxDistance";
    }

    [Flags]
    public enum SettingsChange { None = 0, Enabled = 1, Volume = 2, Range = 4 }
}
```
In `VoiceSettings.cs` (innerhalb der Klasse, nach `Create`) ergänzen:

```csharp
        /// <summary>Neuer Schnappschuss: Datei-Einstellungen (this) mit den gesetzten Menüwerten darüber; gleiche Grenzen wie <see cref="Create"/>.</summary>
        public VoiceSettings WithOverrides(MenuValues values, List<string> warnings)
        {
            return Create(values.Enabled ?? Enabled, values.DialogPercent ?? DialogPercent, values.PlayerPercent ?? PlayerPercent,
                          Language, CacheMegabytes, Diagnostics, warnings, values.BarkPercent ?? BarkPercent,
                          values.BarkMinDistance ?? BarkMinDistance, values.BarkMaxDistance ?? BarkMaxDistance);
        }

        public static SettingsChange Diff(VoiceSettings oldSettings, VoiceSettings newSettings)
        {
            var change = SettingsChange.None;
            if (oldSettings.Enabled != newSettings.Enabled) change |= SettingsChange.Enabled;
            if (oldSettings.DialogPercent != newSettings.DialogPercent || oldSettings.PlayerPercent != newSettings.PlayerPercent
                || oldSettings.BarkPercent != newSettings.BarkPercent) change |= SettingsChange.Volume;
            if (oldSettings.BarkMinDistance != newSettings.BarkMinDistance || oldSettings.BarkMaxDistance != newSettings.BarkMaxDistance)
                change |= SettingsChange.Range;
            return change;
        }
```
Hinweis: `Create` klemmt negatives Min und prüft `!(max > min)` über NaN korrekt; der Test `NaN` (min NaN) landet dabei auf Standardwerten.

- [ ] **Step 4: Tests grün**

Run: `dotnet test mod/DrovaVoice.Core.Tests 2>&1 | tail -1`
Expected: alle grün (192 + 7 neue).

- [ ] **Step 5: Commit**

```bash
git add mod && git commit -m "Add menu values, the settings overlay and change detection"
```

---

### Task 2: VoiceService: austauschbare Einstellungen, Cache nach Lautstärke, Ein/Aus ohne Neustart

**Files:**
- Modify: `mod/DrovaVoice/Playback/VoiceService.cs`, `mod/DrovaVoice/Playback/BarkDistance.cs`, `mod/DrovaVoice/DrovaVoiceMod.cs`

**Interfaces:**
- Consumes: `VoiceSettings`, `SettingsChange`.
- Produces: `VoiceService.Settings` (Lesen), `VoiceService.Apply(VoiceSettings next) : SettingsChange`; `BarkDistance.SetRange(float min, float max)`.
- Keine Core-Logik: Die Verdrahtung ist Unity-Glue; geprüft durch Bau und Spiel (Task 4). Die Cache-Schlüssel-Logik ist ein reiner String und wird im Spiel am Log (`Cache … Clips`) sichtbar.

- [ ] **Step 1: `VoiceService` anpassen**

`_settings` wird austauschbar: `private VoiceSettings _settings;` (nicht `readonly`), dazu

```csharp
        public VoiceSettings Settings => _settings;

        /// <summary>Tauscht die Einstellungen aus (Optionsmenü). Gibt zurück, was sich geändert hat; Clips bleiben im Cache, ihr Schlüssel enthält die Lautstärke.</summary>
        public SettingsChange Apply(VoiceSettings next)
        {
            var change = VoiceSettings.Diff(_settings, next);
            _settings = next;
            if ((change & SettingsChange.Range) != 0) BarkDistance?.SetRange(next.BarkMinDistance, next.BarkMaxDistance);
            return change;
        }
```
In `GetClip` zu Beginn `if (!_settings.Enabled) return null;` und den Cache-Zugriff auf einen Schlüssel mit Prozent umstellen. Die bisherigen Zeilen

```csharp
            if (_store.TryGet(id!, out var cached)) return cached;
            if (_failed.Contains(id!)) return null;

            var clip = _loader.Load(entry, _settings.PercentFor(entry.Category), out long bytes, out long elapsedMs, out string? error);
```
werden zu

```csharp
            int percent = _settings.PercentFor(entry.Category);
            string cacheKey = id + "@" + percent;   // andere Lautstärke = anderer Schlüssel; alte Clips altern aus dem Cache
            if (_store.TryGet(cacheKey, out var cached)) return cached;
            if (_failed.Contains(id!)) return null;

            var clip = _loader.Load(entry, percent, out long bytes, out long elapsedMs, out string? error);
```
und der spätere Aufruf `_store.Put(id!, clip, bytes);` zu `_store.Put(cacheKey, clip, bytes);`. Die Eigenschaften `BarkMinDistance`/`BarkMaxDistance` und `Diagnostics` lesen weiter `_settings` (Felder dürfen sich ändern). Außerdem `HasEntry` unverändert.

- [ ] **Step 2: `BarkDistance.SetRange`**

In `BarkDistance`: `private float _min, _max;` (statt `readonly`), Methode

```csharp
        public void SetRange(float min, float max) { _min = min; _max = max; }
```

- [ ] **Step 3: Vertonung ohne Neustart wieder einschaltbar**

In `DrovaVoiceMod.CreateVoice` den frühen Ausstieg bei `!settings.Enabled` entfernen: die Meldung bleibt (`Vertonung ist ausgeschaltet (Enabled=false); im Optionsmenü einschaltbar.`), der Dienst wird trotzdem erzeugt, wenn der Index lädt. `GetClip` liefert bei `Enabled = false` null, der Connector setzt dann kein Audio.

- [ ] **Step 4: Bauen und Tests**

Spiel geschlossen. Run: `dotnet build mod/DrovaVoice -c Release 2>&1 | grep -E " Fehler|error"` und `dotnet test mod/DrovaVoice.Core.Tests 2>&1 | tail -1`.
Expected: `0 Fehler`, Tests grün.

- [ ] **Step 5: Commit**

```bash
git add mod && git commit -m "Let the voice service swap its settings and key cached clips by volume"
```

---

### Task 3: VoiceMenu: Panel im Optionsmenü, Lesen und Anwenden

**Files:**
- Create: `mod/DrovaVoice/Playback/VoiceMenu.cs`
- Modify: `mod/DrovaVoice/DrovaVoiceMod.cs`

**Interfaces:**
- Consumes: `VoiceService.Settings/Apply`, `MenuValues`, `MenuKeys`, `Drova_Modding_API.Access.OptionMenuAccess`, `OptionUIBuilder`, `LocalizationAccess`, `ConfigAccessor`.
- Produces: `internal sealed class VoiceMenu { public VoiceMenu(VoiceService service, MelonLogger.Instance log); public void Register(); public void LoadFromConfig(); }`.

Die API-Typen sind nur im Spiel prüfbar (Il2Cpp); Namensräume und Aufrufformen beim Bauen anhand des Compilers und der API-DLL (`Mods/Drova_Modding_API.dll`, lesen mit dem Cecil-Werkzeug im Scratchpad) korrigieren. Vorbild: `Drova_Modding_API.Systems.ModdingUI.ModdingUI` (`RegisterModdingUI`, `RegisterLocalization`, `Instance_OnOptionMenuOpen`).

- [ ] **Step 1: `VoiceMenu` schreiben**

Ablauf (Code nach dem Vorbild der API, mit den Schlüsseln aus `MenuKeys` und den Texten unten):

```csharp
using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Drova_Modding_API.Access;
using MelonLoader;

namespace DrovaVoice.Playback
{
    /// <summary>Panel „Drova Voice“ im Optionsmenü des Spiels. Texte deutsch, für jede Spielsprache registriert.</summary>
    internal sealed class VoiceMenu
    {
        private const string ModName = "DrovaVoice";
        private readonly VoiceService _service;
        private readonly MelonLogger.Instance _log;
        private bool _registered, _built, _failed;

        public VoiceMenu(VoiceService service, MelonLogger.Instance log) { _service = service; _log = log; }

        private static readonly (string Key, string Text)[] Texts =
        {
            ("title", "Drova Voice"),
            ("note", "Lautstärke der KI-Stimmen. Über 100 % wird verstärkt. Änderungen gelten ab der nächsten gesprochenen Zeile."),
            ("enabled", "Vertonung"), ("on", "An"), ("off", "Aus"),
            ("dialog", "Dialog-Lautstärke (%)"), ("player", "Spieler-Lautstärke (%)"), ("bark", "Bark-Lautstärke (%)"),
            ("barkMin", "Barks: volle Lautstärke bis (Meter)"), ("barkMax", "Barks: stumm ab (Meter)"),
        };

        public void Register()
        {
            if (_registered) return;
            try
            {
                RegisterTexts();
                OptionMenuAccess.Instance.OnOptionMenuOpen += new OptionMenuAccess.OptionMenuAction(OnOpen);
                OptionMenuAccess.Instance.OnOptionMenuClose += new OptionMenuAccess.OptionMenuAction(OnClose);
                _registered = true;
            }
            catch (Exception e) { Fail("Registrierung", e); }
        }

        private void RegisterTexts()
        {
            var entries = new List<LocalizationAccess.LocalizationEntry>();
            foreach (var language in Enum.GetValues(typeof(ELanguage)))
                foreach (var (key, text) in Texts)
                    entries.Add(new LocalizationAccess.LocalizationEntry(key, text, (ELanguage)language));
            LocalizationAccess.CreateLocalizationEntries(entries, ModName);
        }

        private void OnOpen()
        {
            if (_built || _failed) return;
            try
            {
                var builder = OptionMenuAccess.Instance.GetBuilder(ModName);
                if (builder == null) return;   // die API gibt für eine schon verwendete ID keinen zweiten Builder zurück
                var s = _service.Settings;
                builder.CreateHeader(Text("title"))
                       .CreateDisclaimer(Text("note"))
                       .CreateSwitch(Text("enabled"), Text("on"), Text("off"), MenuKeys.Enabled, s.Enabled, false)
                       .CreateSlider(Text("dialog"), MenuKeys.DialogVolume, 0, 200, s.DialogPercent)
                       .CreateSlider(Text("player"), MenuKeys.PlayerVolume, 0, 200, s.PlayerPercent)
                       .CreateSlider(Text("bark"), MenuKeys.BarkVolume, 0, 200, s.BarkPercent)
                       .CreateSlider(Text("barkMin"), MenuKeys.BarkMinDistance, 0, 200, (int)s.BarkMinDistance)
                       .CreateSlider(Text("barkMax"), MenuKeys.BarkMaxDistance, 10, 400, (int)s.BarkMaxDistance)
                       .Build();
                _built = true;
            }
            catch (Exception e) { Fail("Panel", e); }
        }

        private void OnClose()
        {
            try { LoadFromConfig(); }
            catch (Exception e) { Fail("Werte lesen", e); }
        }

        /// <summary>Liest die Menüwerte aus der Spielkonfiguration (fehlende bleiben null) und wendet sie an.</summary>
        public void LoadFromConfig()
        {
            var values = new MenuValues(
                ReadBool(MenuKeys.Enabled), ReadInt(MenuKeys.DialogVolume), ReadInt(MenuKeys.PlayerVolume), ReadInt(MenuKeys.BarkVolume),
                ReadInt(MenuKeys.BarkMinDistance), ReadInt(MenuKeys.BarkMaxDistance));
            var warnings = new List<string>();
            var next = _service.Settings.WithOverrides(values, warnings);
            foreach (string w in warnings) _log.Warning("Optionsmenü: " + w);
            var change = _service.Apply(next);
            if (change != SettingsChange.None)
                _log.Msg($"Optionsmenü: {change}; Dialog {next.DialogPercent} %, Spieler {next.PlayerPercent} %, Barks {next.BarkPercent} %, Reichweite {next.BarkMinDistance}–{next.BarkMaxDistance}, {(next.Enabled ? "an" : "aus")}.");
        }

        private static int? ReadInt(string key) => ConfigAccessor.TryGetConfigValue<int>(key, out var v) ? v : (int?)null;
        private static bool? ReadBool(string key) => ConfigAccessor.TryGetConfigValue<bool>(key, out var v) ? v : (bool?)null;
        private static Il2CppCustomFramework.Localization.LocalizedString Text(string key) => LocalizationAccess.GetLocalizedString(ModName, key);

        private void Fail(string what, Exception e)
        {
            if (_failed) return;
            _failed = true;
            _log.Warning($"Optionsmenü ({what}): {e.GetType().Name}: {e.Message}. Die Einstellungen aus MelonPreferences.cfg gelten weiter.");
        }
    }
}
```
Anpassungen, die der Compiler/die DLL verlangen kann (jeweils als Ruling im Ledger festhalten): statische vs. Instanzaufrufe von `ConfigAccessor`/`LocalizationAccess`, Namensraum von `LocalizedString` und `ELanguage` (in `DrovaVoiceMod.cs` ist `Il2CppCustomFramework.Localization` schon im Gebrauch), Konstruktor von `LocalizationEntry` (Key, Value, Language), ob `CreateSwitch` einen Bool oder einen Ganzzahlwert in der Konfiguration ablegt (dann `ReadBool` entsprechend über `TryGetConfigValue<int>` lesen: `v != 0`).

- [ ] **Step 2: In der Mod verdrahten**

In `DrovaVoiceMod`: Feld `private VoiceMenu? _menu;`. In `TryInstallConnector` nach dem erfolgreichen Ersetzen des Connectors (dort, wo `_barkDistance` entsteht):

```csharp
                _menu = new VoiceMenu(_voice, LoggerInstance);
                _menu.Register();
                try { _menu.LoadFromConfig(); } catch (Exception) { /* Konfiguration noch nicht bereit: Datei-Einstellungen gelten */ }
```
`LoadFromConfig` beim Start liest gespeicherte Menüwerte (falls vorhanden); fehlen sie, bleiben die Datei-Werte.

- [ ] **Step 3: Bauen**

Spiel geschlossen. Run: `dotnet build mod/DrovaVoice -c Release 2>&1 | grep -E " Fehler|error"`.
Expected: `0 Fehler` (Compilerfehler durch Typnamen wie oben beschrieben beheben und als `Ruling:` ins Ledger).

- [ ] **Step 4: Tests, Commit**

Run: `dotnet test mod/DrovaVoice.Core.Tests 2>&1 | tail -1` (grün).

```bash
git add mod && git commit -m "Add the Drova Voice panel to the game options menu"
```

---

### Task 4: Hörtest im Spiel, Doku

**Files:**
- Modify: `docs/playback.md`, `docs/HANDOFF.md`, `docs/superpowers/specs/2026-10-10-drova-voice-design.md`, Gedächtnis `plan-8-status.md`

- [ ] **Step 1: Nutzer-Test (nur der Nutzer kann ihn ausführen)**

Spiel starten, Optionsmenü öffnen: Es gibt einen Reiter „Modding“/„Drova Voice“ mit Schalter und fünf Reglern. 1. Dialog-Lautstärke auf 200 stellen, Menü schließen, mit einem NPC sprechen: lauter. 2. Barks 0: ein Bark bleibt stumm. 3. Reichweite ändern, Bark nah/fern prüfen. 4. Vertonung „Aus“, Menü schließen: stumm; wieder „An“: Stimmen sind zurück, ohne Neustart. 5. Spiel beenden, neu starten: Die Werte stehen noch im Menü, Log `Optionsmenü: …`.

- [ ] **Step 2: Auswerten und Doku**

Log lesen (`MelonLoader/Latest.log`, Zeilen `Optionsmenü …`). Entscheidungen festhalten: Panel-Name und -Ort, Wert-Format von Schalter und Reglern, Verhalten im Hauptmenü. `docs/playback.md`: Tabelle „Einstellungen“ um den Hinweis ergänzen, dass die Werte im Optionsmenü (Schlüssel `DrovaVoice_*` im Spielspeicher) die Datei überschreiben, sobald sie einmal gesetzt sind; Abschnitt „Regler im Spiel“. `docs/HANDOFF.md`: Stand Plan 8, Zeile „Regler (Dialog, Spieler 0–200 %) vorerst nur per Datei“ ersetzen. Haupt-Spec: Stand-Zeile um „Regler im Spiel erledigt“. Gedächtnis `plan-8-status.md` mit Zeiger in `MEMORY.md`.

- [ ] **Step 3: Commit**

```bash
git add docs && git commit -m "Document the in-game options menu"
```

---

## Self-Review (gegen die Spec)

- Spec „Core“ (MenuValues, WithOverrides, Diff, MenuKeys): Task 1. „Mod“ (VoiceMenu, Anwenden, Start, Texte, Rückfall): Task 2 und 3. „Tests“: Task 1 (Core), Task 4 (Spiel). „Reihenfolge“ mit Probe vorn: Die Probe ist der erste Spieltest der fertigen Mod (Task 4); ein getrenntes Probenprogramm entfällt, weil das Panel selbst klein ist und Fehler im Log landen (Ruling).
- Abweichungen von der Spec: (1) statt den Clip-Cache zu leeren, wird er nach Prozent geschlüsselt (kein Zerstören laufender Clips); (2) Schlüssel mit Unterstrich statt Punkt; (3) Reichweite als Ganzzahl-Regler (Meter).
- Typkonsistenz: `MenuValues`-Felder (`Enabled`, `DialogPercent`, `PlayerPercent`, `BarkPercent`, `BarkMinDistance`, `BarkMaxDistance`) und `MenuKeys` sind in Task 1, 3 gleich benannt; `VoiceService.Apply/Settings` (Task 2) werden in Task 3 verwendet.
- Offene Platzhalter: keine; Typnamen der API sind als „vom Compiler zu bestätigen“ gekennzeichnet.
