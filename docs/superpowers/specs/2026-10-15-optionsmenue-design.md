# Regler im Optionsmenü des Spiels (Design)

Stand 2026-10-15. Baut auf Plan 4 (Wiedergabe) und Plan 7 (Barks) auf. Haupt-Spec §9 („Optionsmenü“), Wiedergabe: `docs/playback.md`.

## Ziel
Der Nutzer stellt **Vertonung an/aus**, **Dialog-**, **Spieler-** und **Bark-Lautstärke** (0 bis 200 %) sowie **Bark-Reichweite** (Min und Max) direkt im Optionsmenü des Spiels ein. Änderungen wirken **ohne Neustart** und bleiben gespeichert. `UserData/MelonPreferences.cfg` bleibt Standard und Rückfall.

Entscheidung des Nutzers (2026-10-15): Umfang „Lautstärken + Barkreichweite“; nicht im Umfang: Schalter je Kategorie, Diagnose-Schalter, Spielerstimm-Sets, Briefe-Regler.

## Befunde (nur DLLs gelesen; im Spiel noch nicht geprüft)
- `Drova_Modding_API` bringt das Optionsmenü-Gerüst mit: `OptionMenuAccess.Instance` (Ereignisse `OnOptionMenuOpen`/`OnOptionMenuClose`, `AddPanel`, `GetBuilder(string id)`) und `OptionUIBuilder` mit `CreateTitle`, `CreateHeader`, `CreateDisclaimer`, `CreateSlider` (Ganzzahl und Kommazahl), `CreateSwitch`, `CreateDropdown`, `CreateButton`, `Build`.
- **Vorbild:** `Drova_Modding_API.Systems.ModdingUI.ModdingUI` registriert sich in `RegisterModdingUI` bei `OnOptionMenuOpen`, holt in `Instance_OnOptionMenuOpen` den Builder und erzeugt Titel, Hinweise und Regler. Texte kommen als `LocalizedString` aus `LocalizationAccess.GetLocalizedString(modName, key)`; Einträge legt `LocalizationAccess.CreateLocalizationEntries(List<LocalizationEntry>, modName)` an.
- **Speicherung:** Ein Regler schreibt bei Änderung über `ConfigGameHandler.GameplayConfig.ConfigFile.SetValue(optionKey, wert.ToString())` in die Konfiguration des Spiels; `ConfigAccessor.TryGetConfigValue<T>(key)` liest sie (Float über String-Parse, Int über `TryGetInt`). Damit entscheidet das Spiel, wann und wohin es schreibt.
- **Unbekannt:** ob die Konfiguration die Werte über Neustarts behält (anzunehmen, da Teil der Spieleinstellungen), ob das Panel im Hauptmenü bereitsteht, und wie die Regler mit Kommazahlen und Ganzzahlen auf dem Bildschirm aussehen.

## Entwurf
### Core (`DrovaVoice.Core`, ohne Spiel testbar)
- `VoiceSettings` bleibt unveränderlich. Neu: `VoiceSettings.WithOverrides(MenuValues values, List<string> warnings)` erzeugt einen neuen Schnappschuss; `MenuValues` hält je Wert ein optionales Feld (`Enabled`, `DialogPercent`, `PlayerPercent`, `BarkPercent`, `BarkMinDistance`, `BarkMaxDistance`). Dieselben Grenzen wie `Create` (0 bis 200 %, Min ≥ 0 und Max > Min, sonst Standard 15 bis 120 mit Warnung).
- `VoiceSettings.Diff(old, new)` liefert, was sich geändert hat: `VolumeChanged` (ein Prozentwert), `RangeChanged`, `EnabledChanged`. Danach entscheidet die Mod, ob der Clip-Cache geleert werden muss.
- `MenuKeys` (Konstanten): `DrovaVoice.Enabled`, `DrovaVoice.DialogVolume`, `DrovaVoice.PlayerVolume`, `DrovaVoice.BarkVolume`, `DrovaVoice.BarkMinDistance`, `DrovaVoice.BarkMaxDistance` (Schlüssel im Konfigurationsspeicher des Spiels).

### Mod
- `VoiceMenu` (Mod): registriert sich einmal bei `OptionMenuAccess.Instance.OnOptionMenuOpen`/`OnOptionMenuClose`. Bei „offen“ baut sie das Panel (Titel, Hinweis, Schalter, fünf Regler) mit Startwerten aus den aktuellen Einstellungen; bei „geschlossen“ liest sie die Werte aus der Spielkonfiguration (`ConfigAccessor`), bildet `WithOverrides`, tauscht den Schnappschuss im `VoiceService` und wendet die Änderung an.
- **Anwenden:** Lautstärken stecken in den dekodierten Samples (`Gain.Apply` im `ClipLoader`): Ändert sich ein Prozentwert, leert `VoiceService` den `ClipStore`; die nächsten Zeilen laden mit neuem Gain, laufende Clips bleiben. Bark-Min/Max gehen an `BarkDistance`; `Enabled` schaltet `GetClip` auf „null“ oder wieder an.
- **Start:** Beim Spielstart gilt: Wert aus der Spielkonfiguration, falls vorhanden, sonst der Wert aus `MelonPreferences`. Die Menüwerte gewinnen, sobald der Nutzer sie einmal gesetzt hat.
- **Texte:** Deutsch, über `LocalizationAccess.CreateLocalizationEntries` beim Start angelegt (Mod-Name `DrovaVoice`), abgerufen mit `GetLocalizedString("DrovaVoice", key)`.
- **Rückfall:** Scheitert das Panel (Typ, Text, Builder), loggt die Mod einmal und läuft mit den Datei-Einstellungen weiter. Ausnahmen in den Menü-Hooks werden immer abgefangen (Haupt-Spec §10).

## Schnittstellen und Grenzen
- `VoiceService` hält einen austauschbaren `VoiceSettings`-Verweis (`Volatile`/Feld, Zugriff nur im Hauptthread des Spiels); `BarkDistance` bekommt `SetRange(min, max)`.
- Keine Änderung am Index, am Audioformat und am Generator.

## Tests
- Core (xUnit, erfundene Werte): `WithOverrides` übernimmt gültige Werte, klemmt 0 bis 200 % mit Warnung, setzt ungültige Reichweite (Max ≤ Min, NaN) auf Standard; fehlende Felder bleiben unverändert; `Diff` erkennt Lautstärke-, Reichweiten- und Ein/Aus-Änderung getrennt; `MenuKeys` sind eindeutig.
- Mod (nur im Spiel): Panel erscheint im Optionsmenü; Regler ändern Lautstärke und Reichweite bei der nächsten Zeile ohne Neustart; Werte bleiben nach Neustart; ohne Panel (Fehlerfall) laufen die Datei-Einstellungen.

## Reihenfolge
0. Probe: Panel mit einem Regler und Schalter bauen, im Hauptmenü und in der Welt öffnen, prüfen, ob die Werte in der Spielkonfiguration ankommen (Log) und Neustarts überleben.
1. Core: `MenuValues`, `WithOverrides`, `Diff`, `MenuKeys` (TDD).
2. Mod: `VoiceMenu` mit allen Reglern, Anwenden, Rückfall.
3. Hörtest und Doku (`docs/playback.md`, `docs/HANDOFF.md`, Haupt-Spec).

## Risiken
- **Texte/Lokalisierung:** `CreateLocalizationEntries` verlangt ein bestimmtes Eintragsformat; die Probe klärt es. Rückfall: Panel ohne Texte wäre unbrauchbar, dann bleibt es bei der Datei.
- **Zeitpunkt:** Im Hauptmenü fehlt eventuell das Optionsfenster; das Panel entsteht dann erst, wenn es da ist (`OnOptionMenuOpen`).
- **Float-Regler:** Das Spiel speichert den Wert als Text; Kultur (Komma/Punkt) kann zum Fehler beim Parsen führen. Die Mod parst mit der invarianten Kultur und fällt bei einem Fehler auf den bisherigen Wert zurück.
- **Rechtliches:** Keine Spieltexte betroffen.
