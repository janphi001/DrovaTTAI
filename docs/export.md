# Export aus dem Spiel (M1)

Voraussetzung: Setup nach `docs/setup.md` (MelonLoader, Modding API, Mod gebaut).

1. Spiel starten und im Hauptmenü warten (`export-npcs` liefert dort 332 statt 420 Einträge mit geladenem Spielstand; der Export mit geladenem Spielstand wurde nur einmal und mit Hänger getestet, siehe unten).
2. Auslöser (eine leere Datei anlegen, die Mod löscht sie beim Erkennen):
   - `<Spiel>/Mods/DrovaVoice/export.trigger`: nur die zurzeit geladenen Dialogbäume (Ergebnis: `manifest-loaded.json`, ersetzt nie den vollständigen Export)
   - `<Spiel>/Mods/DrovaVoice/export-all.trigger`: alle Bäume über den Addressables-Katalog plus die zurzeit geladenen, die dort fehlen (Ergebnis: `manifest.json`; dauert einige Minuten, das Spiel kann währenddessen hängen)
   - `<Spiel>/Mods/DrovaVoice/export-npcs.trigger`: `npcs.json` und `voices.json` (landen im selben `Export/<lang>/`-Ordner wie das Manifest, siehe Punkt 3)
   Alternativ F9 für `export.trigger`, falls die Taste im Spiel funktioniert.
   Liegen `export-all.trigger` und `export.trigger` (oder F9) im selben Frame vor, hat `export-all.trigger` Vorrang.
   Eine Auslöserdatei, die sich nicht löschen lässt, erzeugt einmalig eine Warnung im Log und löst nicht aus; dann die Datei von Hand löschen.
3. Ergebnis: `<Spiel>/Mods/DrovaVoice/Export/<lang>/manifest.json` (vollständig, von `export-all.trigger`) bzw. `manifest-loaded.json` (nur geladene Bäume, von `export.trigger`/F9), dazu `npcs.json`, `voices.json`. Ein leerer oder abgebrochener Export (0 Zeilen, 0 Adressen, Katalog-Laden abgebrochen, leere NPC-/Stimmenliste) lässt vorhandene Dateien unangetastet und meldet den Grund im Log. Die Sprache steht in der MelonLoader-Konfiguration (`ExportLanguage`, Standard `de`); der Text kommt in der aktuellen Spielsprache, bei Abweichung warnt die Mod im Log.
4. Kopieren und prüfen: `drova-voice export fetch`, dann `drova-voice export report` (Exit 0 ab 98 % Abdeckung; für die Datei der geladenen Bäume `drova-voice export report --manifest <Pfad>/manifest-loaded.json`). Fehlende Einträge stehen in `data/export/<lang>/coverage_missing.txt`.

`data/` ist nicht im Git: Das Manifest enthält Spieltexte.

**Stand nach dem ersten Lauf** (Details: `docs/decisions/2026-10-export-findings.md`): Export im Hauptmenü ausführen und das Spiel danach beenden, keinen Spielstand laden (das Spiel hing danach). Das Fenster muss im Vordergrund liegen. `export-all.trigger` (Katalog) funktioniert derzeit nicht; `export.trigger` liefert denselben Umfang, schreibt aber `manifest-loaded.json`: dafür `drova-voice export report --manifest data/export/de/manifest-loaded.json` verwenden.
