# Plan 5: Casting und Vollauf (M4), Entwurf

Stand 2026-10-15. Vom Nutzer im Chat abgenommen (Entwurf, LLM-Vorschlag mit Prüfung durch den Nutzer, Vollauf in Etappen). Bezug: Gesamt-Spec `2026-10-10-drova-voice-design.md` (M4), Übergabe `docs/HANDOFF.md`.

## Ziel und Erfolgskriterium

Im Spiel hat jede sprechbare Dialogzeile eines benannten Sprechers eine zum Charakter passende, wiedererkennbare Stimme. Das sind im Export **11.941 sprechbare Zeilen** (~850.000 Zeichen); davon entfallen 11.528 Zeilen auf **246 benannte Sprecher**, 357 auf generische Sprecher (`NPC`, `Teacher`, `Druid`, `Actor`, `Participant`) und 56 auf den Spieler. Vorhanden sind 41 Stimmen plus 7 Varianten, die Stimmen müssen sich also teilen.

Fertig, wenn
1. jede sprechbare Zeile der benannten Sprecher Audio im Mod-Ordner hat und `report` außer den bekannten Gründen (`gvar`, `unspeakable`, `player_choice`) keine Lücken meldet,
2. der Nutzer die Besetzung nach der Hörstufe abgenommen hat,
3. er stichprobenartig im Spiel gehört hat (Hörtest nimmt er selbst ab).

## Nicht Teil von Plan 5

Varianten für die generischen Sprecher (der Mod braucht dafür die Geschlechtswahl nach `finalActor`, M6), Barks, Briefe, Namensvarianten (`#arden`/`#neutral`), Regler im Spiel, die 98-%-Lücke im Export, Spieler-Stimmsets (M5). Die Spielerzeilen (56 Aussagen) behalten `default_player`.

## Entscheidungen, die für Plan 5 gelten

- **Zuteilung:** Ein LLM *beschreibt* (Steckbrief), ein deterministisches Regelwerk *verteilt*. Das Ergebnis ist wiederholbar, Korrekturen des Nutzers bleiben bei jedem Neulauf erhalten.
- **Vollauf in Etappen:** Pakete nach Wichtigkeit, sauberer Abbruch bei Limit- oder Guthabenfehlern, die Tarifwahl folgt am echten Verbrauch. Fish bekommt Spieltexte **je Etappe erst nach ausdrücklichem Ja des Nutzers**; Haiku-Subagents bekommen Spieltexte nur nach Ja (wie bei `emote` in Plan 3/4).
- Der Fish-Key kommt nur als Umgebungsvariable im Einzelbefehl, er steht nie in Dateien (siehe HANDOFF).

## Bausteine

### 1. Steckbriefe (`profile`)

- Datei `casting/profiles.jsonl`, eine Zeile je Sprecher: `speaker`, `gender` (`m|f`), `age` (`kind|jung|mittel|alt`), `type` (optional, eines von `riese|zwerg|schurke`, sonst leer), `confidence` (0..1), `note` (ein kurzer Satz zum Charakter, **ohne wörtliche Zitate**, weil `casting/` im Git liegt), `source` (`llm|manual`).
- Neue Befehle `profile --prepare` (schreibt je Paket von ~20 Sprechern eine Eingabedatei im Scratchpad: Zeilen des Sprechers, Baumnamen, Zeilen, in denen andere ihn ansprechen oder erwähnen; **keine Datei im Git**) und `profile --import <Datei>` (prüft das JSON-Schema, nimmt nur bekannte Sprecher an, überschreibt keine `manual`-Zeilen). Haiku-Subagents erledigen die Pakete (nur lesend, eine Ausgabedatei).
- Das Geschlecht darf nie allein aus dem Namen geraten werden (Femke ist ein Mann); der Auftrag verlangt, aus Anrede, Pronomen und Rolle zu schließen. Unsichere Zeilen (`confidence < 0.6`) erscheinen in der Prüfliste hervorgehoben.
- Die 6 bereits besetzten Sprecher bekommen Steckbriefe mit `source: manual` aus ihrer bisherigen Besetzung.

### 2. Zuteilung (`cast --propose`)

- Eingabe: Steckbriefe, `casting/fish_voices.yaml` (Stimmen und Varianten), Zeilenzahlen und Bäume je Sprecher aus `data/lines.jsonl`.
- Ausgabe: `casting/casting_auto.yaml` (erzeugt, im Git). Die handgepflegte `casting/casting.yaml` bleibt wie sie ist und **gewinnt** bei Überschneidung; so bleiben Kommentare und Festlegungen des Nutzers erhalten. `load_casting` liest beide Dateien (Auto zuerst, dann die manuelle darüber).
- Kandidaten: Stimmen und Varianten. Die Varianten bekommen dafür in `fish_voices.yaml` die Felder `age` und `type` (zum Beispiel `riese`: `age: mittel, type: riese`, `knabe`: `age: kind`, `alte_frau`: `age: alt`).
- Regelwerk, deterministisch (Sprecher nach Zeilenzahl absteigend, Gleichstand nach Name):
  1. Hartes Filter: Geschlecht.
  2. Punkte: Alter passt (exakt 0, benachbart Abzug), Typ passt (Bonus für Riese/Zwerg/Schurke/Kind/Alte).
  3. Abzug je bereits vergebener Verwendung der Stimme (gewichtet mit der Zeilenzahl dieser Sprecher), damit markante Stimmen bei wichtigen Figuren zuerst landen und die Last gleichmäßig verteilt wird.
  4. **Starker Abzug**, wenn ein Sprecher mit derselben Stimme im selben Dialogbaum vorkommt (Stimmenwiederholung innerhalb einer Szene vermeiden).
  5. Gleichstand: Stimmenschlüssel alphabetisch.
- Bereits manuell besetzte Sprecher zählen als vergeben (Vorbelegung), werden aber nie verändert.
- Sprecher ohne brauchbaren Steckbrief (Geschlecht fehlt) werden im Ergebnis ausdrücklich als offen gemeldet und nicht geraten.
- `cast --check` meldet zusätzlich: Stimmen mit auffälliger Überbelegung (mehr als N Sprecher), Paare mit gleicher Stimme im selben Baum.

### 3. Hörstufe vor dem Vollauf

- `--sample` als Auswahl für `synth`, `encode`, `preview`: je Sprecher **eine** Beispielzeile (bevorzugt mittellang, 40 bis 120 Zeichen, mit Emotion, falls vorhanden). Rund 246 Zeilen, wenige Minuten, kaum Zeichen.
- Die Beispiel-WAVs haben denselben Cache-Schlüssel wie im Vollauf. Bleibt die Besetzung, sind sie keine verlorene Arbeit; ändert der Nutzer eine Stimme, wird nur diese Zeile neu erzeugt.
- Hörseite `out/casting/index.html` (Erweiterung von `preview`): Spalten Sprecher, Zeilen, Geschlecht/Alter laut Steckbrief, Stimme, Audio, Beispieltext. Sortiert nach Zeilenzahl. Der Nutzer notiert Korrekturen in `casting/casting.yaml` (`name: {voice: schlüssel}`).
- Erst nach der Abnahme der Hörstufe beginnt der Vollauf.

### 4. Varianten

- In `casting*.yaml` darf `voice:` ein Variantenschlüssel sein. Eine Variante wird mit der **Basisstimme** erzeugt (Cache-Schlüssel der Basis, kein Mehrverbrauch bei Fish) und beim Kodieren umgeformt.
- Umsetzung in `encode`: Das Rezept (`asetrate`, `aresample`, `rubberband` mit `pitch`, `tempo`, `formant=preserved`, siehe Kommentar in `fish_voices.yaml`) wird dem Filter `build_filter` vorangestellt. Der Stempel (`.stamp`) enthält den Filter, geänderte Rezepte erzwingen daher automatisch neu Kodieren.
- Voraussetzung: ffmpeg mit `rubberband` (auf diesem Rechner vorhanden); `find_tools` prüft das, sobald eine Variante vorkommt.
- `install`, `report` und die Hörseite bleiben unverändert, weil die Datei pro Zeile-ID abgelegt wird.

### 5. Emotionen für alle Zeilen

- `emote` (Regeln aus Regieanweisungen) läuft über alle Zeilen; danach markieren Haiku-Subagents je Dialogbaum (alle Zeilen am Stück plus Steckbriefe der Sprecher) die klaren Emotionen.
- Neue Hilfen `emote --prepare` und `emote --import <Datei>` (Schema-Prüfung gegen `EmotionTag`, nur bekannte Zeilen-IDs, `llm`-Zeilen überschreiben nie `manual`). Auftragstext wie in Plan 3 Task 9: zurückhaltend, `neutral`/`mundane` nicht ausgeben, `events` nur, wenn der Text den Laut nennt.
- 1.405 Bäume mit sprechbaren Zeilen; Pakete zu ~20 Bäumen.

### 6. Etappen und Vollauf

- `drova-voice batches` plant die Pakete: Sprecher nach Wichtigkeit (Zeilenzahl), Pakete bis ~100.000 Zeichen (rund neun Pakete), schreibt `data/batches.json` und druckt Sprecher, Zeilen und Zeichen je Paket.
- `--batch N` als Auswahl für `synth`, `encode`, `install`, `report`.
- **Abbruchregel in `synth`:** Wiederholen sich Fehler der Art Guthaben/Limit/Authentifizierung (Schwelle zum Beispiel 10 in Folge), bricht der Lauf sauber ab, nennt den Grund und lässt bereits Erzeugtes im Cache. Der nächste Lauf setzt fort. Die genauen Fehlertexte des Fish-Workers werden in der Planphase aus `workers/` und `engines/client.py` ermittelt.
- Verbrauch: `synth` und `report` zeigen erzeugte Zeichen (neu gegenüber Cache) je Lauf und kumuliert; so lässt sich Tarif und Restbedarf am echten Verbrauch entscheiden.
- Ablauf je Etappe: Ja des Nutzers für Fish → `synth --batch N` → `encode --batch N` → `install --batch N` → `report`. Bei Fehlern erneut starten.

### 7. Berichte

- `report --by-speaker`: Zeilen, erzeugt, kodiert, installiert, Lücken je Sprecher. Ende von Plan 5: alle Sprecher grün.

## Dateien und Git

Ins Git: `casting/profiles.jsonl`, `casting/casting_auto.yaml`, `casting/casting.yaml`, `casting/emotions.jsonl`, erweiterte `casting/fish_voices.yaml`, Code und Tests. **Nicht** ins Git: Eingabedateien für Subagents, `data/`, `cache/`, `out/` (enthalten Spieltexte). Tests verwenden erfundene Texte und erfundene Sprecher.

## Tests

- Zuteilung: feste Eingaben erzeugen eine feste Ausgabe; Geschlecht ist hart; manuelle Einträge bleiben; Wiederholung im selben Baum wird vermieden; Sprecher ohne Steckbrief bleiben offen.
- `casting.yaml` überschreibt `casting_auto.yaml`; gemeinsames Laden meldet unbekannte Stimmen und Varianten wie bisher.
- Varianten: Rezept erscheint im ffmpeg-Filter, Stempel ändert sich mit dem Rezept, Variante nutzt den Cache-Schlüssel der Basisstimme.
- Auswahl: `--sample` wählt genau eine Zeile je Sprecher, `--batch` genau die Zeilen der Paketsprecher.
- Abbruchregel von `synth` mit einem Fake-Client, der Limitfehler liefert.
- `profile --import` und `emote --import` lehnen unbekannte Sprecher/Zeilen und ungültige Werte ab.

## Risiken

- **Tarif/Limit unbekannt:** Etappen und Abbruchregel fangen das ab; Kitten bleibt lokale Rückfallebene, aber nicht Teil von Plan 5.
- **Zu wenige passende Stimmen** (Kinder, alte Frauen, helle Männer): Die Zuteilung meldet dies als „Notbesetzung“ (Typ passt nicht), der Nutzer entscheidet bei der Hörstufe. Neue Stimmen sind ein späterer Auswahlauftrag.
- **Falsches Geschlecht aus dem LLM:** Prüfliste mit Konfidenz, Hörstufe als Gegenprobe, `manual`-Zeilen gewinnen.
- **Stimmwiederholung** bei 246 Sprechern ist unvermeidlich; das Regelwerk begrenzt sie auf nicht gleichzeitig auftretende Figuren.
