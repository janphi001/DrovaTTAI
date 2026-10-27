# Wiedergabe in der Mod

Die Mod spielt die vom Generator erzeugten Stimmen im Spiel ab. Grundlage: `docs/audio-format.md` (Vertrag), Entwurf: `docs/superpowers/specs/2026-10-14-plan-4-wiedergabe-design.md`.

## So funktioniert es

1. Beim Start liest die Mod `Mods/DrovaVoice/Audio/<AudioLanguage>/index.json`. Fehlt sie oder passt Version oder Sprache nicht, bleibt die Vertonung aus und das Spiel läuft unverändert. Danach prüft sie etwa einmal pro Sekunde (alle 60 Frames) Länge und Schreibzeit. Hat sich eines davon geändert, liest sie den Index neu, leert den Clip-Cache und vergisst Zeilen, die bisher fehlgeschlagen sind. Dieselbe Prüfung erzwingt eine leere Datei `Mods/DrovaVoice/reload.trigger` (die Mod löscht sie). Schlägt das Lesen fehl, steht der Grund einmal im Log; ein schon geladener Index bleibt aktiv. Zwei weitere Versuche, etwa alle fünf Sekunden und ohne neue Meldung, holen eine Datei nach, die beim ersten Mal gerade ersetzt wurde.
2. Sobald das Spiel in einer Welt ist (`WorldEventSystemManager.Instance` existiert), ersetzt die Mod den Audio-Connector der Modding API durch den eigenen. Vorher nicht: Im Hauptmenü scheitert `AudioManager` und bliebe die ganze Sitzung kaputt.
3. Führt das Spiel eine Aussage aus, fragt die API den Connector (nur wenn die Zeile noch keinen Clip hat). Der Connector bildet die Zeilen-ID (Baum, Loca-Pfad, Schlüssel), sucht sie im Index, dekodiert die OGG-Datei (NVorbis), wendet die Lautstärke an und erzeugt den `AudioClip`. Barks hängt er an die Zeile (`statement.audio`), das Spiel spielt sie ab. Dialog- und Spielerzeilen spielt die Mod selbst (`DialogueVoice`, siehe unten).
4. Bei Auswahlknoten, die die Auswahl sprechen (`saySelection`), lädt ein Harmony-Prefix auf `DS_MultipleChoiceNode.OnExecute` die Clips aller Optionen (ID mit `|c<Index>`), damit die gewählte Option gesprochen wird. Er ist erst aktiv, nachdem der Connector ersetzt wurde. Verschiebt das Spiel die Optionsliste, findet die Mod die Option über ihren Schlüssel.
5. Geladene Clips bleiben im Cache (Standard 64 MB). Verdrängte Clips werden zerstört und beim nächsten Mal neu geladen; die 8 jüngsten werden nie verdrängt.

Zeilen ohne Eintrag bleiben stumm, die Untertitel laufen wie im Original. Das betrifft auch Zeilen mit Spielernamen mitten im Satz (`gvar_name`) und Zeilen mit Quest- oder Geldwerten ohne saubere neutrale Fassung (`gvar_value`). Wo sich der Spielername streichen lässt oder ein Wert vor einem bekannten Nomen steht, spricht die Mod die neutrale Fassung (`…#neutral`): ohne Namen und mit fester Menge statt Zahl („ein paar Münzen“, „etwas Gold“). Die Untertitel zeigen weiter den Namen und die echte Zahl.

## Einstellungen

Datei: `<Spiel>/UserData/MelonPreferences.cfg`, Abschnitt `[DrovaVoice]` (entsteht beim ersten Start mit der neuen Mod). Änderungen gelten **nach einem Neustart des Spiels**.

| Schlüssel | Standard | Bereich | Bedeutung |
|---|---|---|---|
| `Enabled` | `true` | — | Vertonung an/aus |
| `DialogVolume` | `100` | 0–200 | NPC-Stimmen in Prozent; über 100 wird verstärkt (mit weichem Begrenzer) |
| `PlayerVolume` | `100` | 0–200 | Spielerzeilen in Prozent |
| `BarkVolume` | `100` | 0–200 | Welt-Kommentare (Barks) in Prozent |
| `BarkMinDistance` | `15` | 0–500 | Barks: bis zu diesem Abstand zum Spieler (Weltmeter) volle Lautstärke |
| `BarkMaxDistance` | `120` | > Min, höchstens 500 | Barks: ab diesem Abstand stumm, dazwischen linear leiser (laufend, auch beim Annähern wieder lauter) |
| `BarkProbe` | `false` | — | Entwicklung: pro Aussage Figur (Name, Körpertyp, VoiceID, GUID, Abstand) loggen |
| `AudioLanguage` | `de` | — | Unterordner unter `Mods/DrovaVoice/Audio` |
| `CacheMB` | `64` | 8–512 | Obergrenze für geladene Clips |
| `Diagnostics` | `false` | — | Jede Zeile einmal loggen (geladen / ohne Eintrag) |
| `ExportLanguage` | `de` | — | Ordnername des Exports (siehe `docs/export.md`) |
| `OwnDialogueVoice` | `true` | — | Dialog- und Spielerzeilen über eine eigene AudioSource, damit der Skip wie ohne Stimme wirkt (siehe „Dialogstimme und Skip“); `false` = Wiedergabe durch das Spiel |

Die Dateien sind auf −16 LUFS normiert; wie laut das im Verhältnis zu Musik und Effekten wirkt, muss man im Spiel hören. 100 % lässt die Dateien bit-genau unverändert; ab 101 % begrenzt ein weicher Begrenzer Spitzen über 0,8, damit nichts hart übersteuert (über alle 255 Dateien, Dialog und Spieler, erreicht der höchste Peak 0,91).

## Log-Meldungen (`MelonLoader/Latest.log`)

| Meldung | Bedeutung |
|---|---|
| `Index: N Zeilen (M übersprungen) …` | Index gelesen; M = Einträge mit kaputtem Format oder unsicherem Pfad |
| `Index neu geladen: N Zeilen …` | index.json hat sich geändert oder `reload.trigger` lag; Cache und gemerkte Ladefehler sind leer |
| `Kein index.json unter …` / `Index nicht nutzbar …` | Vertonung bleibt aus; Pfad, Version, Sprache prüfen. Die Meldung kommt einmal, bis die Datei sich ändert |
| `index.json fehlt unter …; der bisherige Index bleibt.` / `Index nicht neu geladen …` | Nachladen ist fehlgeschlagen; die schon geladenen Zeilen bleiben |
| `DrovaTTS ist geladen …` | DrovaTTS ist ebenfalls installiert; eine der beiden Mods bleibt stumm (siehe README, Kompatibilität) |
| `Audio-Connector der Modding API ersetzt.` | Wiedergabe aktiv (erscheint erst in der Welt, innerhalb eines Frames nach `WorldEventSystemManager.Instance`) |
| `Connector konnte nicht ersetzt werden …` | `AudioManager` ist kaputt (z. B. durch einen zu frühen Zugriff einer anderen Mod); Vertonung bleibt aus |
| `Zeile bleibt stumm (…): <ID>` | Datei fehlt oder ist defekt; nur einmal pro ID, bis der Index neu geladen wird |
| `Laden dauerte N ms (Ruckler möglich): <ID>` | Zeile wurde trotzdem abgespielt; typisch nur bei der allerersten Zeile (JIT, kalter Dateicache) |
| `[Zeile] Option … -> … (Index der Option hat sich verschoben)` | Das Spiel hat die Optionsliste verändert; der Eintrag wurde über den Schlüssel gefunden (nur `Diagnostics`) |
| `[Zeile] Auswahlknoten … spricht die Auswahl nicht (saySelection aus)` | Der Knoten bleibt wie im Original ohne Spielerstimme (nur `Diagnostics`) |
| `Export im Hauptmenü: …` | Ein Export im Hauptmenü macht die Vertonung in dieser Sitzung wirkungslos; Spiel neu starten |
| `[Zeile] geladen: <ID> …` / `[Zeile] ohne Eintrag: <ID>` | nur mit `Diagnostics = true` |

Ob die DrovaTTS-Warnung im Log steht und ob eine nachgeladene Zeile hörbar ist, zeigt nur ein laufendes Spiel. Wann nachgeladen und wann geloggt wird, prüfen die Tests in `mod/DrovaVoice.Core.Tests`.

## Abnahme-Checkliste (im Spiel)

1. `Diagnostics = true` setzen, Spiel starten: Log zeigt `Index: 255 Zeilen …`, im Hauptmenü **keine** `TypeInitializationException`.
2. Spielstand laden: `Audio-Connector der Modding API ersetzt.`
3. Adela ansprechen: `[Zeile] geladen …`, Stimme hörbar, Untertitel synchron. Zeilen mit Spielernamen sprechen die neutrale Fassung (ohne Namen), sofern sich der Name streichen lässt. Zeilen mit Geldwerten vor einem bekannten Nomen sagen „ein paar Münzen“ oder „etwas Gold“, der Untertitel die echte Zahl. Zeilen mit dem Namen mitten im Satz und die übrigen Zeilen mit Quest- oder Geldwerten bleiben stumm (Untertitel wie im Original); das ist erwartet und kein Fehler.
4. Auswahl erscheint: Spielerzeilen laden (`Player`), die gewählte Option wird gesprochen.
5. Zeile überspringen und Fenster mit Esc schließen: verstummt die Stimme? Läuft das Gespräch danach normal weiter?
6. Jero (234 Zeilen): keine Ruckler, Cache bleibt unter 64 MB.
7. `DialogVolume`/`PlayerVolume` ändern (z. B. 150 / 80), neu starten: hörbar anders. 250 wird mit Warnung auf 200 begrenzt.

## Bekannte Grenzen

- Der Spieler spricht seine gewählte Antwortoption nicht (wie im Original); der Generator erzeugt dafür keine Dateien (`player_choice`). Der Auswahl-Hook der Mod ist deshalb nur eine Reserve, falls später Optionsdateien im Index stehen.
- Spielerstimm-Sets fehlen noch. Bei Zeilen mit streichbarem Spielernamen oder neutral sprechbarem Quest-/Geldwert gilt `…#neutral`, sonst die Basis-ID; Zeilen mit nicht streichbarem Namen und die übrigen Quest-/Geldwerte bleiben stumm. Die Stimme nennt nie die echte Zahl.
- Briefe haben noch keine Dateien und keine Regler.

## Dialogstimme und Skip

- Hängt ein Clip an `statement.audio`, behandelt das Dialogfeld des Spiels (`DS_DialogueUGUI`) die Stimme beim Skip als eigene Stufe: Der erste Druck beendet nur die Stimme, der Text tippt in normaler Geschwindigkeit weiter, erst weitere Drücke schalten weiter. Ohne Clip vervollständigt der erste Druck den Text. Im Spiel gemessen (2026-10-20).
- Deshalb spielt `DialogueVoice` Dialog- und Spielerzeilen auf einer eigenen `AudioSource` am Objekt des Dialogfelds (Einstellungen von der Quelle des Spiels dort: 3D-Anteil, Reichweite, Mixer). Start: Prefix auf `OnSubtitlesRequest` im selben Bild wie der Connector. Ende: nächste Zeile desselben Dialogfelds, `OnDialogueFinished`/`OnDialoguePaused`, oder ein Tastendruck ab 0,25 s nach dem Start (Skip). Weltzeilen, deren Text in der Sprechblase steht (`…/WorldBox/…`), skippt das Spiel nicht; die Mod beendet sie deshalb auch nicht per Taste (sonst brach z. B. ein Angriff im Kampf die Stimme ab).
- Tempo: Mit Clip an der Aussage tippt das Spiel den Text über die Cliplänge, ohne Clip etwa 70 Zeichen/s. Solange die Stimme läuft, begrenzt `DialogueVoice` in `OnLateUpdate` die sichtbaren Zeichen des Gesprächsfensters (`…/SubtitlesGroup/Speech`) auf den Anteil der Clipzeit (`TextPace`), höchstens bis zum Stand des Spiels. Das Textfeld kommt direkt aus dem Fenster des Dialogfelds (`WindowMgr._currentWindowControl.CurrentWindow.SubtitlesGroup.ActorSpeech`). Eine Suche über alle Textfelder (`FindObjectsOfType<TextMeshProUGUI>`) kostete rund 20 ms je Aufruf und ließ die Bildrate bei jeder gesprochenen Zeile eine Sekunde lang einbrechen (gemessen 2026-10-21: 142–169 statt 238 fps). Ein Postfix auf `InitializeText` löst nicht aus (läuft in der Text-Coroutine).
- Messung: Mit `BarkProbe = true` schreibt die Mod jede Sekunde eine `[Bilder]`-Zeile (fps, schlechtestes Bild, Zeit der Mod je Abschnitt, Audioquellen, Barkbilder, GC). Beim Ende oder Skip bekommt das Textfeld den Stand des Spiels zurück.
- Barks laufen weiter über `statement.audio` (kein Skip, Entfernung über `BarkDistance`).
- `OwnDialogueVoice = false` in `MelonPreferences.cfg` schaltet zurück auf die Wiedergabe durch das Spiel (dann wieder der Skip in zwei Stufen).
- Harmony-Patches auf `DS_DialogueUGUI` werden von Hand angelegt. Methoden, die nur innerhalb der Text-Coroutine laufen (`HandleAudio`, `IterateText`, `SkipTextAnimation` …), lassen sich nicht abfangen; `SkipTextAnimation` von außen aufzurufen ändert nichts, weil die Coroutine `maxVisibleCharacters` mit ihrem eigenen Zähler überschreibt.

## Optionsmenü (Plan 8)
- Im Optionsmenü des Spiels gibt es das Panel **Drova Voice** (über die Modding API, `OptionMenuAccess`/`OptionUIBuilder`): Schalter Vertonung, Regler Dialog, Spieler und Barks (0–200 %), Barks volle Lautstärke bis (Meter) und stumm ab (Meter). Änderungen gelten ab der nächsten Zeile, ohne Neustart; die Mod liest sie beim Schließen des Menüs aus der Spielkonfiguration (Schlüssel `DrovaVoice_Enabled`, `DrovaVoice_DialogVolume`, `…PlayerVolume`, `…BarkVolume`, `…BarkMinDistance`, `…BarkMaxDistance`).
- **Datei und Menü:** `MelonPreferences.cfg` liefert die Startwerte. Sobald das Menü das erste Mal geöffnet wurde, hat die Spielkonfiguration alle Schlüssel (der Builder schreibt die Startwerte hinein) und überstimmt ab dann die Datei bei jedem Start. Wer die Datei wieder maßgeblich machen will, löscht die `DrovaVoice_*`-Schlüssel in der Spielkonfiguration.
- Die Lautstärke steckt im geladenen Clip (`Gain` beim Dekodieren). Der Clip-Cache ist nach `id@prozent` geschlüsselt, alte Clips altern aus dem Cache. Damit eine neue Lautstärke auch bei schon gehörten Zeilen ankommt, wird **jeder** Clip nach dem Abspielstart wieder von der Aussage genommen (`BarkDistance.Watch`); der Connector läuft dann bei jeder Ausführung neu.
- Ist die Vertonung im Menü aus (oder `Enabled=false`), ersetzt die Mod den Connector der API trotzdem und liefert keinen Clip; so lässt sie sich ohne Neustart wieder einschalten.
- Die Texte sind für die Sprachen angemeldet, deren Ordner unter `Drova_Data/StreamingAssets/Localization/` existiert (die API schreibt dort `DrovaVoice_<Sprache>.loc`).
- Überlappen Min und Max im Menü (Min ≥ Max), bleibt das Min stehen und das Max rückt auf Min + 10 (mit einer Warnung, je Text einmal geloggt). Ein fehlender Menüwert fällt auf den Wert aus `MelonPreferences.cfg` zurück.
- Scheitert das Panel, loggt die Mod `Optionsmenü …` einmal und läuft mit den Datei-Einstellungen weiter.

## Barks und Stimmenpool (Plan 7)
- Barks (Welt-Kommentare, Kampfrufe) liegen unter `bark/` (Kategorie `Bark`, Regler `BarkVolume`). Generische Sprecher (`NPC`, Teacher …) haben keine eigene Stimme: Der Index führt je Zeile Varianten `#vm1…`, `#vw1…` (Pool aus `casting/pools.yaml`).
- Die Mod liest zur Laufzeit die sprechende Figur (`FigureReader`: Körpertyp `Strong`=m, `Petite`=w, GUID) und wählt mit `PoolVoice.Pick` (Rendezvous-Hashing über die GUID) eine feste Poolstimme. Dieselbe Figur klingt immer gleich; ist die Figur nicht lesbar, entscheidet die Zeilen-ID (kein Absturz). Befund der Probe: `docs/decisions/2026-10-bark-figur-probe.md`.
- Lehrer: Die Lehrgespräche (Sprecher `Teacher`, z. B. `DT_Quest_Generic_Teach_*`) haben zusätzlich je Lehrer eine Variante `#t_<loca-schlüssel>` (z. B. `#t_carima`) in dessen eigener Stimme. `PoolVoice.Resolve` nimmt sie, wenn der Loca-Schlüssel der EntityInfo der sprechenden Figur passt, sonst die Poolstimme. Die Lehrerliste steht in `casting/teachers.yaml` (aus `teachers.json`, siehe `docs/export.md`).
- **Falle:** Die Aussage eines Barks ist für alle Figuren dieselbe, und `statement.audio` bleibt nach dem ersten Setzen stehen. Dann ruft die API den Connector bei Wiederholungen nicht mehr auf (falsche Stimme, keine Entfernungsregelung). `BarkDistance` setzt `statement.audio` deshalb wieder auf `null`, sobald der Clip spielt (Log mit `Diagnostics`: `[Bark] Aussage freigegeben`).
- Starten zwei Figuren dieselbe Bark-Aussage im selben Frame, setzt `StatementHook` den Clip auf null, bevor der API-Prefix den Connector überspringt. Die Entscheidung ist `StatementGate.ClearAttachedClip`, die Priorität liegt über dem API-Prefix. Ob die Reihenfolge im Spiel greift, ist ohne die Spiel-Assemblies nicht geprüft.
- Entfernung: Die API dämpft Barks nicht (`docs/decisions/2026-10-bark-entfernung.md`); `BarkDistance` regelt `AudioSource.volume` in jedem Frame nach dem Abstand zum Spieler und stellt die Lautstärke am Ende wieder her.
- `BarkDistance` und die Audio-Sonde teilen sich eine Suche (`AudioSourceScan`, alle 0,25 s, `ScanScheduler`). `FindObjectsOfType` läuft nicht mehr jeden Frame und nicht mehr doppelt. Die Sonde zählt einen stillen Clip nur je Suche (zwei Suchen, etwa 0,5 s), nicht je Frame.
- Keine Regler im Spiel; Werte nur per Datei und Neustart.
- OGG wird im ThreadPool dekodiert (`OggDecoder`, `Gain`). `AudioClip.Create` und `SetData` bleiben auf dem Hauptthread. Der Connector wartet auf das PCM (Obergrenze 5 s), damit `statement.audio` im selben Aufruf gesetzt werden kann. Liegt die Wartezeit über 500 ms, kommt weiter die Warnung `Laden dauerte …`; die Zeile wird trotzdem abgespielt.
