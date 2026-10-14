# Wiedergabe in der Mod

Die Mod spielt die vom Generator erzeugten Stimmen im Spiel ab. Grundlage: `docs/audio-format.md` (Vertrag), Entwurf: `docs/superpowers/specs/2026-10-14-plan-4-wiedergabe-design.md`.

## So funktioniert es

1. Beim Start liest die Mod `Mods/DrovaVoice/Audio/<AudioLanguage>/index.json`. Fehlt sie oder passt Version oder Sprache nicht, bleibt die Vertonung aus und das Spiel läuft unverändert.
2. Sobald das Spiel in einer Welt ist (`WorldEventSystemManager.Instance` existiert), ersetzt die Mod den Audio-Connector der Modding API durch den eigenen. Vorher nicht: Im Hauptmenü scheitert `AudioManager` und bliebe die ganze Sitzung kaputt.
3. Führt das Spiel eine Aussage aus, fragt die API den Connector (nur wenn die Zeile noch keinen Clip hat). Der Connector bildet die Zeilen-ID (Baum, Loca-Pfad, Schlüssel), sucht sie im Index, dekodiert die OGG-Datei (NVorbis), wendet die Lautstärke an und hängt den `AudioClip` an die Zeile. Abgespielt wird er vom Spiel; die Untertitel laufen passend zur Cliplänge.
4. Bei Auswahlknoten lädt ein Harmony-Prefix auf `DS_MultipleChoiceNode.OnExecute` die Clips aller Optionen (ID mit `|c<Index>`), damit die gewählte Option gesprochen wird.
5. Geladene Clips bleiben im Cache (Standard 64 MB). Verdrängte Clips werden zerstört und beim nächsten Mal neu geladen; die 8 jüngsten werden nie verdrängt.

Zeilen ohne Eintrag (und Zeilen mit `$GVAR:`) bleiben stumm, die Untertitel laufen wie im Original.

## Einstellungen

Datei: `<Spiel>/UserData/MelonPreferences.cfg`, Abschnitt `[DrovaVoice]` (entsteht beim ersten Start mit der neuen Mod). Änderungen gelten **nach einem Neustart des Spiels**.

| Schlüssel | Standard | Bereich | Bedeutung |
|---|---|---|---|
| `Enabled` | `true` | — | Vertonung an/aus |
| `DialogVolume` | `100` | 0–200 | NPC-Stimmen in Prozent; über 100 wird verstärkt (mit weichem Begrenzer) |
| `PlayerVolume` | `100` | 0–200 | Spielerzeilen in Prozent |
| `AudioLanguage` | `de` | — | Unterordner unter `Mods/DrovaVoice/Audio` |
| `CacheMB` | `64` | 8–512 | Obergrenze für geladene Clips |
| `Diagnostics` | `false` | — | Jede Zeile einmal loggen (geladen / ohne Eintrag) |
| `ExportLanguage` | `de` | — | Ordnername des Exports (siehe `docs/export.md`) |

Die Dateien sind auf −16 LUFS normiert; wie laut das im Verhältnis zu Musik und Effekten wirkt, muss man im Spiel hören. 100 % lässt die Dateien bit-genau unverändert; ab 101 % begrenzt ein weicher Begrenzer Spitzen über 0,8, damit nichts hart übersteuert (die lautesten Dateien erreichen 0,91).

## Log-Meldungen (`MelonLoader/Latest.log`)

| Meldung | Bedeutung |
|---|---|
| `Index: N Zeilen (M übersprungen) …` | Index gelesen; M = Einträge mit kaputtem Format oder unsicherem Pfad |
| `Kein index.json unter …` / `Index nicht nutzbar …` | Vertonung bleibt aus; Pfad, Version, Sprache prüfen |
| `Audio-Connector der Modding API ersetzt.` | Wiedergabe aktiv (erscheint erst in der Welt) |
| `Connector konnte nicht ersetzt werden …` | `AudioManager` ist kaputt (z. B. durch einen zu frühen Zugriff einer anderen Mod); Vertonung bleibt aus |
| `Zeile bleibt stumm (…): <ID>` | Datei fehlt/defekt/zu langsam (über 500 ms); nur einmal pro ID |
| `[Zeile] geladen: <ID> …` / `[Zeile] ohne Eintrag: <ID>` | nur mit `Diagnostics = true` |

## Abnahme-Checkliste (im Spiel)

1. `Diagnostics = true` setzen, Spiel starten: Log zeigt `Index: 255 Zeilen …`, im Hauptmenü **keine** `TypeInitializationException`.
2. Spielstand laden: `Audio-Connector der Modding API ersetzt.`
3. Adela ansprechen: `[Zeile] geladen …`, Stimme hörbar, Untertitel synchron. Zeilen mit `$GVAR:` bleiben stumm.
4. Auswahl erscheint: Spielerzeilen laden (`Player`), die gewählte Option wird gesprochen.
5. Zeile überspringen und Fenster mit Esc schließen: verstummt die Stimme? Läuft das Gespräch danach normal weiter?
6. Jero (234 Zeilen): keine Ruckler, Cache bleibt unter 64 MB.
7. `DialogVolume`/`PlayerVolume` ändern (z. B. 150 / 80), neu starten: hörbar anders. 250 wird mit Warnung auf 200 begrenzt.

## Bekannte Grenzen

- Namensvarianten (`#arden`/`#neutral`) und Spielerstimm-Sets fehlen noch; es gilt die Basis-ID.
- Barks und Briefe haben noch keine Dateien und keine Regler.
- Keine Regler im Spiel; Werte nur per Datei und Neustart.
- Das Dekodieren läuft synchron auf dem Hauptthread (Zeilen sind kurz); Hintergrund-Vorladen gibt es erst, wenn die Messung Ruckler zeigt.
