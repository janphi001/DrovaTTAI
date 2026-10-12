# Export aus dem Spiel (M1)

Voraussetzung: Setup nach `docs/setup.md` (MelonLoader, Modding API, Mod gebaut).

1. Spiel starten und im Hauptmenü warten (für `export-npcs` einen Spielstand laden).
2. Auslöser (eine leere Datei anlegen, die Mod löscht sie beim Erkennen):
   - `<Spiel>/Mods/DrovaVoice/export.trigger`: nur die zurzeit geladenen Dialogbäume
   - `<Spiel>/Mods/DrovaVoice/export-all.trigger`: alle Bäume über den Addressables-Katalog (dauert einige Minuten, das Spiel kann währenddessen hängen)
   - `<Spiel>/Mods/DrovaVoice/export-npcs.trigger`: `npcs.json` und `voices.json` (landen im selben `Export/<lang>/`-Ordner wie das Manifest, siehe Punkt 3)
   Alternativ F9 für `export.trigger`, falls die Taste im Spiel funktioniert.
   Liegen `export-all.trigger` und `export.trigger` (oder F9) im selben Frame vor, hat `export-all.trigger` Vorrang.
   Eine Auslöserdatei, die sich nicht löschen lässt, erzeugt einmalig eine Warnung im Log und löst nicht aus; dann die Datei von Hand löschen.
3. Ergebnis: `<Spiel>/Mods/DrovaVoice/Export/<lang>/manifest.json` (+ `npcs.json`, `voices.json`). Die Sprache steht in der MelonLoader-Konfiguration (`ExportLanguage`, Standard `de`); der Text kommt in der aktuellen Spielsprache.
4. Kopieren und prüfen: `drova-voice export fetch`, dann `drova-voice export report` (Exit 0 ab 98 % Abdeckung). Fehlende Einträge stehen in `data/export/<lang>/coverage_missing.txt`.

`data/` ist nicht im Git: Das Manifest enthält Spieltexte.
