# Wiedergabe in der Mod

Die Mod spielt die vom Generator erzeugten Stimmen im Spiel ab. Grundlage: `docs/audio-format.md` (Vertrag), Entwurf: `docs/superpowers/specs/2026-10-14-plan-4-wiedergabe-design.md`.

## So funktioniert es

1. Beim Start liest die Mod `Mods/DrovaVoice/Audio/<AudioLanguage>/index.json`. Fehlt sie oder passt Version oder Sprache nicht, bleibt die Vertonung aus und das Spiel läuft unverändert.
2. Sobald das Spiel in einer Welt ist (`WorldEventSystemManager.Instance` existiert), ersetzt die Mod den Audio-Connector der Modding API durch den eigenen. Vorher nicht: Im Hauptmenü scheitert `AudioManager` und bliebe die ganze Sitzung kaputt.
3. Führt das Spiel eine Aussage aus, fragt die API den Connector (nur wenn die Zeile noch keinen Clip hat). Der Connector bildet die Zeilen-ID (Baum, Loca-Pfad, Schlüssel), sucht sie im Index, dekodiert die OGG-Datei (NVorbis), wendet die Lautstärke an und hängt den `AudioClip` an die Zeile. Abgespielt wird er vom Spiel; die Untertitel laufen passend zur Cliplänge.
4. Bei Auswahlknoten, die die Auswahl sprechen (`saySelection`), lädt ein Harmony-Prefix auf `DS_MultipleChoiceNode.OnExecute` die Clips aller Optionen (ID mit `|c<Index>`), damit die gewählte Option gesprochen wird. Er ist erst aktiv, nachdem der Connector ersetzt wurde. Verschiebt das Spiel die Optionsliste, findet die Mod die Option über ihren Schlüssel.
5. Geladene Clips bleiben im Cache (Standard 64 MB). Verdrängte Clips werden zerstört und beim nächsten Mal neu geladen; die 8 jüngsten werden nie verdrängt.

Zeilen ohne Eintrag bleiben stumm, die Untertitel laufen wie im Original. Das betrifft auch Zeilen mit Spielernamen mitten im Satz (`gvar_name`) und Zeilen mit Quest- oder Geldwerten (`gvar_value`). Nur wo sich der Spielername streichen lässt, spricht die Mod die neutrale Fassung (`…#neutral`, Untertitel zeigen weiter den Namen).

## Einstellungen

Datei: `<Spiel>/UserData/MelonPreferences.cfg`, Abschnitt `[DrovaVoice]` (entsteht beim ersten Start mit der neuen Mod). Änderungen gelten **nach einem Neustart des Spiels**.

| Schlüssel | Standard | Bereich | Bedeutung |
|---|---|---|---|
| `Enabled` | `true` | — | Vertonung an/aus |
| `DialogVolume` | `100` | 0–200 | NPC-Stimmen in Prozent; über 100 wird verstärkt (mit weichem Begrenzer) |
| `PlayerVolume` | `100` | 0–200 | Spielerzeilen in Prozent |
| `BarkVolume` | `100` | 0–200 | Welt-Kommentare (Barks) in Prozent |
| `BarkMinDistance` | `15` | ≥ 0 | Barks: bis zu diesem Abstand zum Spieler (Weltmeter) volle Lautstärke |
| `BarkMaxDistance` | `120` | > Min | Barks: ab diesem Abstand stumm, dazwischen linear leiser (laufend, auch beim Annähern wieder lauter) |
| `BarkProbe` | `false` | — | Entwicklung: pro Aussage Figur (Name, Körpertyp, VoiceID, GUID, Abstand) loggen |
| `AudioLanguage` | `de` | — | Unterordner unter `Mods/DrovaVoice/Audio` |
| `CacheMB` | `64` | 8–512 | Obergrenze für geladene Clips |
| `Diagnostics` | `false` | — | Jede Zeile einmal loggen (geladen / ohne Eintrag) |
| `ExportLanguage` | `de` | — | Ordnername des Exports (siehe `docs/export.md`) |

Die Dateien sind auf −16 LUFS normiert; wie laut das im Verhältnis zu Musik und Effekten wirkt, muss man im Spiel hören. 100 % lässt die Dateien bit-genau unverändert; ab 101 % begrenzt ein weicher Begrenzer Spitzen über 0,8, damit nichts hart übersteuert (über alle 255 Dateien, Dialog und Spieler, erreicht der höchste Peak 0,91).

## Log-Meldungen (`MelonLoader/Latest.log`)

| Meldung | Bedeutung |
|---|---|
| `Index: N Zeilen (M übersprungen) …` | Index gelesen; M = Einträge mit kaputtem Format oder unsicherem Pfad |
| `Kein index.json unter …` / `Index nicht nutzbar …` | Vertonung bleibt aus; Pfad, Version, Sprache prüfen |
| `Audio-Connector der Modding API ersetzt.` | Wiedergabe aktiv (erscheint erst in der Welt, innerhalb eines Frames nach `WorldEventSystemManager.Instance`) |
| `Connector konnte nicht ersetzt werden …` | `AudioManager` ist kaputt (z. B. durch einen zu frühen Zugriff einer anderen Mod); Vertonung bleibt aus |
| `Zeile bleibt stumm (…): <ID>` | Datei fehlt oder ist defekt; nur einmal pro ID |
| `Laden dauerte N ms (Ruckler möglich): <ID>` | Zeile wurde trotzdem abgespielt; typisch nur bei der allerersten Zeile (JIT, kalter Dateicache) |
| `[Zeile] Option … -> … (Index der Option hat sich verschoben)` | Das Spiel hat die Optionsliste verändert; der Eintrag wurde über den Schlüssel gefunden (nur `Diagnostics`) |
| `[Zeile] Auswahlknoten … spricht die Auswahl nicht (saySelection aus)` | Der Knoten bleibt wie im Original ohne Spielerstimme (nur `Diagnostics`) |
| `Export im Hauptmenü: …` | Ein Export im Hauptmenü macht die Vertonung in dieser Sitzung wirkungslos; Spiel neu starten |
| `[Zeile] geladen: <ID> …` / `[Zeile] ohne Eintrag: <ID>` | nur mit `Diagnostics = true` |

## Abnahme-Checkliste (im Spiel)

1. `Diagnostics = true` setzen, Spiel starten: Log zeigt `Index: 255 Zeilen …`, im Hauptmenü **keine** `TypeInitializationException`.
2. Spielstand laden: `Audio-Connector der Modding API ersetzt.`
3. Adela ansprechen: `[Zeile] geladen …`, Stimme hörbar, Untertitel synchron. Zeilen mit Spielernamen sprechen die neutrale Fassung (ohne Namen), sofern sich der Name streichen lässt. Zeilen mit dem Namen mitten im Satz und Zeilen mit Quest- oder Geldwerten bleiben stumm (Untertitel wie im Original); das ist erwartet und kein Fehler.
4. Auswahl erscheint: Spielerzeilen laden (`Player`), die gewählte Option wird gesprochen.
5. Zeile überspringen und Fenster mit Esc schließen: verstummt die Stimme? Läuft das Gespräch danach normal weiter?
6. Jero (234 Zeilen): keine Ruckler, Cache bleibt unter 64 MB.
7. `DialogVolume`/`PlayerVolume` ändern (z. B. 150 / 80), neu starten: hörbar anders. 250 wird mit Warnung auf 200 begrenzt.

## Bekannte Grenzen

- Der Spieler spricht seine gewählte Antwortoption nicht (wie im Original); der Generator erzeugt dafür keine Dateien (`player_choice`). Der Auswahl-Hook der Mod ist deshalb nur eine Reserve, falls später Optionsdateien im Index stehen.
- Spielerstimm-Sets fehlen noch. Bei Zeilen mit streichbarem Spielernamen gilt `…#neutral`, sonst die Basis-ID; Zeilen mit nicht streichbarem Namen oder Quest-/Geldwerten bleiben stumm.
- Briefe haben noch keine Dateien und keine Regler.

## Barks und Stimmenpool (Plan 7)
- Barks (Welt-Kommentare, Kampfrufe) liegen unter `bark/` (Kategorie `Bark`, Regler `BarkVolume`). Generische Sprecher (`NPC`, Teacher …) haben keine eigene Stimme: Der Index führt je Zeile Varianten `#vm1…`, `#vw1…` (Pool aus `casting/pools.yaml`).
- Die Mod liest zur Laufzeit die sprechende Figur (`FigureReader`: Körpertyp `Strong`=m, `Petite`=w, GUID) und wählt mit `PoolVoice.Pick` (Rendezvous-Hashing über die GUID) eine feste Poolstimme. Dieselbe Figur klingt immer gleich; ist die Figur nicht lesbar, entscheidet die Zeilen-ID (kein Absturz). Befund der Probe: `docs/decisions/2026-10-bark-figur-probe.md`.
- **Falle:** Die Aussage eines Barks ist für alle Figuren dieselbe, und `statement.audio` bleibt nach dem ersten Setzen stehen. Dann ruft die API den Connector bei Wiederholungen nicht mehr auf (falsche Stimme, keine Entfernungsregelung). `BarkDistance` setzt `statement.audio` deshalb wieder auf `null`, sobald der Clip spielt (Log mit `Diagnostics`: `[Bark] Aussage freigegeben`).
- Entfernung: Die API dämpft Barks nicht (`docs/decisions/2026-10-bark-entfernung.md`); `BarkDistance` regelt `AudioSource.volume` in jedem Frame nach dem Abstand zum Spieler und stellt die Lautstärke am Ende wieder her.
- Keine Regler im Spiel; Werte nur per Datei und Neustart.
- Das Dekodieren läuft synchron auf dem Hauptthread (Zeilen sind kurz); Hintergrund-Vorladen gibt es erst, wenn die Messung Ruckler zeigt.
