# DrovaVoice – KI-Vertonung für Drova: Forsaken Kin (Design)

Stand: 2026-10-10 · Status: Entwurf zur Freigabe; §15 enthält die Änderungen nach dem Hörtest (M2)

## 1. Ziel

Drova: Forsaken Kin (Just2D, Unity 2022.3.45f1, IL2CPP) hat keine Sprachausgabe. DrovaVoice vertont die Texte des Spiels mit lokal erzeugten KI-Stimmen:

- NPC-Dialoge (Gesprächsfenster)
- Spielerfigur (Stimme wählbar)
- Welt-Kommentare/Barks (eigene Lautstärke, abhängig von der Entfernung)
- Briefe und Tagebücher

**Zielgruppe:** zuerst privat für den Autor. Das Repo bleibt veröffentlichbar: Es enthält nur Code und Konfiguration, **keine Spieltexte und kein Audio**. Andere Nutzer erzeugen die Audiodateien selbst mit dem Generator.

**Sprache:** zuerst Deutsch (Originalsprache). Englisch und weitere Sprachen sind später nur ein weiterer Durchlauf (eigener Audio-Ordner pro Sprache).

**Erfolgskriterium:** Ein Spieler hört beim normalen Durchspielen jede NPC-Dialogzeile mit einer passenden, wiedererkennbaren Stimme und plausibler Emotion. Die Untertitel laufen synchron dazu, ohne Wartezeit und ohne Abstürze.

## 2. Ausgangslage (verifiziert)

| Fakt | Quelle |
|---|---|
| Unity 2022.3.45f1, IL2CPP (`GameAssembly.dll`), Dialoge = NodeCanvas DialogueTrees | Spielordner, `globalgamemanagers` |
| Alle Texte liegen offen als `.loc` unter `Drova_Data/StreamingAssets/Localization/<lang>/…`, Format `Key { Text }` | Spielordner |
| Deutsch: ca. 18.300 Dialogzeilen, ca. 1,21 Mio. Zeichen (≈ 22 h Audio) | Zählung `Dialog*/`, `Dialogues/`, `*World*.loc` |
| Die Keys (`Plh_<n>`) sind nur pro Datei eindeutig. In NPC-Dateien sind Spieler- und NPC-Zeilen gemischt, ein Sprecher ist nur im DialogueTree hinterlegt | Stichprobe `NPC_Adela_de.loc` |
| 1.716 Zeilen enthalten Regieanweisungen `*grinst*`, `*seufzt*`, `*flüstert*`, `*hick*` … | Zählung |
| 508 Zeilen enthalten `$GVAR:<Set>.<Var>$`. Davon 233 mit dem Spielernamen (frei wählbar, Standard „Arden“), der Rest überwiegend feste Quest-Konfigurationswerte aus dem `GlobalVarSystem`, wenige Laufzeitwerte | Zählung, Bundle-Analyse |
| Das Spiel kennt `ActorGenderSettings`/`Gender`/`isMale`, `ActorBodyType`, `VoiceID`/`VoiceMap`, `EntityPortrait`, Stimmwahl im Charakter-Editor (`GUI_DresserOption_Voice`) | `global-metadata.dat` |
| Drova Modding API 0.5.4 (MIT, MelonLoader ≥ 0.7.0): Audio-Hooks (`IAudioConnector`/`IAudioHandler`/`IAudioProvider`, Harmony-Patches auf `Graph.SelfDeserialize`, `DS_StatementNode.OnExecute`, `DS_MultipleChoiceNode.OnOptionSelected`, `DS_DialogueUGUI.OnSubtitlesRequest`), Optionsmenü, Config, `DialogueAudioDistanceManager`. Ein Dialog-Exporter `CreateTTSDialogueFile` existiert nur im Debug-Build und ist deaktiviert | API-Quellcode |
| Hardware: RTX 3080 (10 GB), Python 3.10, .NET SDK 9/10, ffmpeg 7 | lokal geprüft |

Das alte Repo `DrovaTTSAI` (SAPI-Echtzeit-TTS) wird nicht weiterverwendet. Übernommen werden nur Ideen: Filter für SVM-Bäume, Optionsmenü-Muster.

## 3. Architektur

Ansatz: **Offline-Pipeline mit Export im Spiel.** Laufzeit-TTS kommt später optional dazu (M8).

```
DrovaTTAI/
├─ mod/
│   ├─ DrovaVoice/            MelonLoader-Mod (net6, IL2CPP, referenziert Drova Modding API)
│   │   ├─ Export/            Dialog-Export
│   │   ├─ Playback/          Connector, Handler, Clip-Cache, Kategorien
│   │   └─ Settings/          Optionsmenü + Config
│   ├─ DrovaVoice.Core/       reine Logik ohne Il2Cpp (IDs, Varianten, Pfade) – testbar
│   └─ DrovaVoice.Core.Tests/ xUnit
├─ generator/                 Python-CLI `drova-voice`
│   ├─ drova_voice/           Pipeline-Schritte
│   ├─ engines/<name>/        je Engine eigene venv + Worker
│   └─ tests/                 pytest
├─ casting/                   casting.yaml, emotions.jsonl, name_variants.jsonl, lexicon.yaml (nur IDs/Labels, ins Git)
├─ tests/vectors/             gemeinsame Testvektoren für C# und Python
├─ data/                      Export, lines.jsonl, Steckbriefe, Porträts   (gitignored)
├─ voices/                    Stimmen-Pool                                  (gitignored)
├─ cache/, out/               WAV-Cache, OGG-Ausgabe                        (gitignored)
└─ docs/
```

**Datenfluss**

1. Spiel + Mod (Export) → `data/export/<lang>/manifest.json`, `npcs.json`, `gvars.json`, `portraits/*.png`
2. Generator: `extract` → `dossier` → `cast` → `emote` → `synth` → `encode` → `install`
3. Spiel + Mod (Wiedergabe) → `<Spiel>/Mods/DrovaVoice/Audio/<lang>/index.json` + OGG-Dateien → Clip an der Dialogzeile → Abspielen über die Audioquelle des Spiels

## 4. Zeilen-Identität und Dateien

**Zeilen-ID** (identisch in C# und Python, abgesichert über `tests/vectors/line_ids.json`):

- Aussage: `{treeName}|{locaPath}|{locaKey}`
- Auswahloption: `{treeName}|{locaPath}|{locaKey}|c{choiceIndex}`. Der Index ist nötig, weil sich in der API zwei Optionen mit gleichem Key gegenseitig überschreiben.
- `locaPath` ist `GlobalLocaPath`, wenn `useGlobalLoca` gesetzt ist, sonst der `LocaPath` des Baums, jeweils mit `/` normalisiert.

**Varianten-Suffix** (optional, durch `#` getrennt): `#m1`, `#f2` (generische Sprecher), `#arden`/`#neutral` (Spielername).

**Dateiablage:** `Audio/<lang>/<kategorie>/<sha1(id)[:16]>.ogg`. Spielerzeilen liegen unter `Audio/<lang>/player/<set>/…`. `index.json` bildet die ID samt Variante auf die Datei, die Dauer und die vorhandenen Varianten ab. Der Hash-Dateiname vermeidet Probleme mit Pfadlänge und Sonderzeichen. Der Mod liest nur `index.json` und muss keine Dateinamen selbst bilden.

## 5. Mod: Export

- Auslöser: Taste (Standard F9) im Hauptmenü, alternativ eine Schaltfläche im Optionsmenü.
- **Bäume vollständig laden:** alle `DT_*`-Adressen aus `StreamingAssets/aa/catalog.json` per Addressables laden, ergänzt um `Resources.FindObjectsOfTypeAll<DialogueTree>()`. Danach `SelfDeserialize()`/`DeserializeIfNotDoneYet(true)` und alle Knoten durchgehen. Unterbäume (`SubDialogueTree`) und generische Sprecher werden nach dem Vorbild von `CreateTTSDialogueFile` behandelt (MIT, mit Quellenangabe).
- **Pro Zeile** in `manifest.json`:
  - `id`, `tree`, `nodeId`, `nodeType` (statement/choice/world), `choiceIndex`
  - `actorName`, `category` (dialog/player/bark/letter)
  - `locaPath`, `locaKey`
  - `text` (über `GetLocalizedString()` in der aktuellen Spielsprache)
  - `gvars` (Liste der Platzhalter)
  - `next`/`prev` (Knotenverbindungen, als Kontext für Emotionen)
- **Kategorie:** Ist der Sprecher der Spieler, wird es `player`. SVM- und Welt-Bäume (`DT_World*`, `DT_Generic_Combat_*`, `DT_Comment_*`, `*_WorldDialogue(s)`) werden `bark`. Alles andere wird `dialog`. Unabhängig von der Kategorie bekommen generische Sprecher (`NPC`, `TEACHER`, `INSTIGATOR`, `DRUID`, `Participant`, `ACTOR`) das Flag `generic` und damit Varianten (§9).
- `npcs.json`: interner Name, Anzeigename (`NPC_Names`), Geschlecht, `VoiceID`, Körpertyp, Porträt-Pfad. Wo genau diese Daten liegen, wird in M1 geklärt.
- `gvars.json`: aktueller Wert jeder verwendeten Variable direkt aus dem `GlobalVarSystem`, eingestuft als `config` oder `runtime` (Laufzeitwerte nicht einsetzen).
- **Abdeckungsbericht:** Abgleich gegen alle Dialog-Einträge der `.loc`-Dateien. Ziel ist, dass ≥ 98 % der Einträge in `Dialog*/Dialogues/*World*` im Manifest stehen, und der Bericht listet die fehlenden auf.

## 6. Generator (Python-CLI `drova-voice`)

`config.yaml`: Spielpfad, Sprache, Engine, Pfade.

| Schritt | Aufgabe |
|---|---|
| `extract` | `manifest.json` → `data/lines.jsonl`. Briefe kommen zusätzlich direkt aus `Letters/*.loc` (Parser für mehrzeilige Einträge). Den Sprechtext erzeugen: Regieanweisungen `*…*` entfernen und als Hinweise speichern, Tags entfernen, `<br>` wird zur Pause, `$GVAR` mit `config`-Wert einsetzen, Zahlen in Wörter umwandeln (Deutsch), `lexicon.yaml` anwenden. Zeilen mit `runtime`-Variablen werden als `skip_runtime` markiert. |
| `dossier` | Pro Sprecher eine Datei `data/dossiers/<npc>.md`: Spieldaten, Porträt, etwa 30 typische Zeilen, Häufigkeit. |
| `cast` | Haiku-Subagents (in Claude Code) schlagen pro NPC vor: Stimme aus dem Pool, Geschlecht, Altersgruppe, Charakternotiz, Tempo. Ergebnis ist `casting/casting.yaml`, das der Nutzer prüft. `cast --check` meldet Sprecher ohne Stimme und Stimmen, die übermäßig oft vergeben sind. |
| `emote` | Haiku-Subagents bekommen pro Dialogbaum alle Zeilen am Stück plus die Steckbriefe der Sprecher und schreiben `casting/emotions.jsonl` (siehe §7). Regieanweisungen sind dabei feste Signale. Manuelle Korrekturen bleiben bei einem neuen Lauf erhalten. |
| `names` | Für die 233 Zeilen mit Spielernamen in `casting/name_variants.jsonl` (siehe §8). |
| `synth` | Ruft den Engine-Worker auf. Cache-Schlüssel ist ein Hash aus Engine, Modellversion, Stimme, Sprechtext, Emotion und Parametern. Der Lauf ist fortsetzbar und sortiert nach Stimme. Plausibilitätsprüfung: Die Dauer muss zur Textlänge passen, sonst wird die Zeile mit max. 2 Versuchen neu erzeugt und danach im Bericht markiert. Sehr kurze Zeilen („Hmpf.“, „…“) bekommen eine Sonderbehandlung (Laute oder Mindestlänge). |
| `encode` | ffmpeg: Stille trimmen, Lautheit auf −16 LUFS angleichen, OGG Vorbis mono. `*flüstert*` → leiser und gehauchter (Filter). |
| `install` | Kopiert nach `<Spiel>/Mods/DrovaVoice/Audio/<lang>/` und schreibt `index.json`. |
| `preview`, `regen`, `report` | Probehören (pro NPC oder Emotion), gezielt neu erzeugen, Abdeckung pro Kategorie anzeigen. |

**Engine-Worker:** Jede Engine liegt unter `generator/engines/<name>/` mit eigener venv und einem Worker-Skript. Das Protokoll ist JSON-Lines über stdin/stdout:
- Anfrage: `{text, voice_ref|voice_name, emotion, intensity, events, emphasis, params}`
- Antwort: `{wav_path, sample_rate, duration}`

Der Generator kennt nur dieses Protokoll. Für M8 bekommt derselbe Worker einen HTTP-Modus.

**Kandidaten für den Hörtest (M2):** Kitten TTS 2 (Stellon Community License), Chatterbox Multilingual (MIT), XTTS-v2 (CPML, nicht-kommerziell; das ist zulässig, weil kein Audio verteilt wird).

**Stimmen-Pool** unter `voices/<id>/`: `ref.wav` und `meta.yaml` (Geschlecht, Altersgruppe, Klangfarbe, Quelle, Lizenz). Ziel sind 30–40 unterscheidbare deutsche Stimmen. Woher die Referenzen kommen, entscheidet M2: eingebaute Engine-Stimmen, CC0-Aufnahmen aus Mozilla Common Voice, eigene Aufnahmen oder ein Modell, das Stimmen aus einer Beschreibung erzeugt.

## 7. Emotionen

Engine-neutrales Format pro Zeilen-ID in `emotions.jsonl`:

```json
{"id": "...", "emotion": "stern", "intensity": 0.6, "events": [{"tag": "sigh", "pos": 0}], "emphasis": ["nie"], "source": "llm|stage|manual"}
```

- `emotion` ∈ {neutral, angry, contemplative, excited, joyful, mundane, nervous, sad, stern, surprised, tender}
- `events` ∈ {gasp, giggle, growl, gulp, laugh, pause, scoff, sigh, sob, um}. `pos` ist die Position als Zeichenindex im Sprechtext.
- Regieanweisungen werden fest übersetzt, z.B. `*seufzt*` → sigh, `*lacht*` → laugh, `*grinst*`/`*lächelt*` → joyful mit niedriger Intensität, `*hick*` → Betrunkenheit (Notiz), `*flüstert*` → Nachbearbeitung im `encode`-Schritt.
- **Zurückhaltung als Regel:** Standard ist neutral oder mundane, Laute nur bei klarem Hinweis im Text.
- **Übersetzung pro Engine:** Kitten nutzt die Tags direkt (`[emotion]` am Zeilenanfang, `<event>` im Satz, `(((Wort)))`). Chatterbox setzt Emotion und Intensität in „exaggeration“ um und lässt die Laute weg. XTTS wählt bei Bedarf eine passende Referenzaufnahme.

## 8. Spielername

- Variante `#arden`: `$GVAR:EVars_Player.Name$` → „Arden“ (Standardname).
- Variante `#neutral`:
  - Steht der Name als Anrede (≈ 150 Zeilen, z.B. „Hallo [NAME]!“), wird er entfernt und die Zeichensetzung korrigiert.
  - Steht er im Satz (≈ 80 Zeilen), schlägt das LLM pro Zeile einen Ersatz vor („Held“, „Fremder“, „der Neue“, oder eine Umformulierung wie „Ich komme von weit her.“). Der Nutzer prüft die Vorschläge.
- Laufzeit: Heißt der Spieler „Arden“, wird `#arden` gespielt, sonst `#neutral`. Der Untertitel zeigt immer den echten Namen.

## 9. Mod: Wiedergabe

- **Laden bei Bedarf statt beim Laden des Baums:** `OnDialogueTreeLoaded` legt nur einen Index an und hängt **keine** Clips an. So ruft der API-Patch auf `DS_StatementNode.OnExecute` bei jeder Zeile `OnWorldDialogueStatement` auf. Dort wird der Clip über `index.json` gefunden, mit NVorbis dekodiert und an `statement.audio` gehängt. Clips der direkten Nachfolgeknoten werden im Hintergrund vorab geladen. Ein LRU-Cache mit Obergrenze (Standard 64 MB PCM) begrenzt den Speicher.
- **Auswahloptionen:** Die Clips der Optionen werden beim Anzeigen des Auswahlknotens geladen, damit `OnOptionSelected` sie vorfindet.
- **Varianten:**
  - Spielerzeilen kommen aus dem gewählten Set. „Auto“ richtet sich nach der Stimme oder dem Körpertyp aus dem Charakter-Editor.
  - Generische Sprecher bekommen eine Variante nach dem Geschlecht von `finalActor` und stabil nach dessen Namen (gleicher NPC, gleiche Stimme).
  - Der Spielername bestimmt die Namensvariante (§8).
- **Handler:** Die Untertitel laufen synchron zur echten Clip-Länge. Beim Überspringen oder Schließen verstummt die Stimme. Wird ein Fenster nie angezeigt, bricht ein Timeout das Warten ab.
- **Lautstärke:** Regler für Dialog, Spieler, Barks und Briefe. Barks werden zusätzlich mit einstellbarer Reichweite abgeschwächt. Überschreibt der `DialogueAudioDistanceManager` der API unsere Werte, übernimmt der Mod die Entfernungslogik für seine Quellen selbst (wird in M6 geklärt).
- **Briefe:** eigener Harmony-Hook auf die Brief-Oberfläche (Klasse wird in M7 ermittelt) mit eigener AudioSource und Erzähler- bzw. Autorstimme.
- **Fehlerverhalten:** Fehlt eine Datei, ist sie defekt oder dauert das Dekodieren länger als 500 ms, bleibt die Zeile stumm und die Untertitel laufen wie im Original. Jede ID wird nur einmal geloggt. Ausnahmen in Hooks werden immer abgefangen.
- **Optionsmenü:**
  - Vertonung an/aus
  - Kategorien an/aus
  - vier Lautstärken
  - Reichweite der Barks
  - Spielerstimme (Auto/Set)

## 10. Meilensteine

| # | Inhalt | Abnahme |
|---|---|---|
| M0 | Setup: MelonLoader und Modding API installieren, Il2Cpp-Assemblies erzeugen, C#-Projekte mit Spielpfad aus `Directory.Build.props`/Umgebungsvariable, Python-Grundgerüst, `.gitignore` | Leerer Mod meldet sich im MelonLoader-Log |
| M2 | Hörtest (parallel zu M0, braucht nur `.loc`-Text): 3 Engines × ca. 30 Zeilen (verschiedene NPC-Typen, Emotionen, kurze Zeilen, Namen), Test der Quellen für Referenzstimmen, Messung der Geschwindigkeit | Entscheidung des Nutzers zu Engine und Stimmen-Pool, festgehalten in `docs/decisions/` |
| M1 | Export inklusive `npcs.json`, `gvars.json`, Porträts, Abdeckungsbericht. Klärt die Risiken R1 und R4 | Abdeckung ≥ 98 %, Anteil der Spielerzeilen bekannt |
| M3 | Durchstich mit einem NPC (Adela): alle Generator-Schritte, Wiedergabe für Dialog und Spieler. Klärt R5 | Adela ist im Spiel synchron hörbar |
| M4 | Casting und Emotionen für alle NPCs, komplette Generierung, `report` | 100 % der vertonbaren Dialogzeilen vorhanden |
| M5 | Spieler-Stimmsets (Anzahl nach M1, vermutlich 2) mit „Auto“ | Umschalten im Spiel funktioniert |
| M6 | Barks: Varianten für generische Sprecher, Reichweite, Lautstärke. Klärt R2 | Barks leiser und entfernungsabhängig |
| M7 | Briefe: Hook und Erzählerstimme. Klärt R3 | Brief wird vorgelesen |
| M8 | Optional: Laufzeit-TTS (Worker im HTTP-Modus) für `runtime`-Variablen und den echten Spielernamen | — |

## 11. Risiken

| # | Risiko | Gegenmaßnahme |
|---|---|---|
| R1 | Nicht alle Bäume lassen sich außerhalb des Spielflusses laden | Addressables-Adressen aus dem Katalog nutzen, Abdeckungsbericht. Notfalls `.loc`-Dateien mit LLM-Sprecherzuordnung als Ersatz |
| R2 | Der DistanceManager überschreibt die Lautstärke pro Kategorie | Eigene Entfernungslogik |
| R3 | Die Klasse der Brief-Oberfläche ist unbekannt | In M7 per Il2Cpp-Assemblies suchen |
| R4 | Geschlecht und Stimm-ID sind schwer erreichbar | Ersatz: Schätzung durch das LLM aus Steckbrief und Porträt |
| R5 | Unklar, ob Dialoge nach dem Clip automatisch weiterlaufen | In M3 beobachten, Handler daran anpassen |
| R6 | Zu wenig deutsche Stimmvielfalt oder schlechte Klonqualität | M2 zuerst, mehrere Quellen für Referenzen |
| R7 | Kurze Zeilen und Fantasienamen klingen falsch | Sonderbehandlung, `lexicon.yaml`, Plausibilitätsprüfung |
| R8 | Die Generierung dauert lange (geschätzt 8–20 h) | Fortsetzbarer Cache, nur geänderte Zeilen neu erzeugen, Lauf über Nacht |
| R9 | Patch des Spiels oder der API bricht den Mod | Versionen in der Doku festhalten, Hooks robust mit try/catch |

## 12. Tests

- **Python (pytest):**
  - `.loc`-Parser (mehrzeilige Einträge, Tags)
  - Sprechtext (Regieanweisungen, `<br>`, Zahlen, GVAR, Lexikon)
  - Varianten des Spielernamens
  - Cache-Schlüssel
  - Übersetzung der Emotionen pro Engine
  - Bildung der IDs und Hashes gegen `tests/vectors/`
- **C# (xUnit, `DrovaVoice.Core`):**
  - Bildung der IDs und Hashes gegen dieselben Vektoren
  - Variantenwahl (Geschlecht, stabiler Hash, Spielername, Spieler-Set)
  - Lesen von `index.json`
  - LRU-Cache
- **Im Spiel:** Checkliste pro Meilenstein. Das Log zeigt pro Baum die Zeilen, die vertont sind, und die fehlenden.

## 13. Arbeitsweise

- Gut abgegrenzte Aufgaben erledigen Haiku-Subagents: Parser, Tests, Engine-Worker, Pakete für Casting, Emotionen und Namen.
- Heikle Il2Cpp-Hooks, Integration und Review übernimmt die Hauptsitzung.
- Downloads ins System oder in den Spielordner (MelonLoader, API-Release, Modelle) werden vorher einzeln mit dem Nutzer abgestimmt.

## 14. Nicht im Umfang (YAGNI)

- Lippensynchronität und Porträt-Animation
- Verteilung von Audio
- Echtzeit-Gespräche per LLM
- Andere Sprachen als Deutsch in Version 1

## 15. Änderungen nach dem Hörtest (M2, 2026-10-10)

Quelle: `docs/decisions/2026-10-tts-engine.md`. Wo dieser Abschnitt der übrigen Spec widerspricht, gilt dieser Abschnitt.

- **Engine:** Fish Audio (Cloud, API `https://api.fish.audio/v1/tts`, Modell `s2.1-pro-free` bzw. `s2.1-pro`) mit den **offiziellen deutschen Fish-Stimmen** (Lena, Leon, Melanie, Lukas (Österreich), Emma, Elin (Schweiz), Jonas, Valentina (Österreich)). Die Aussagen "lokal erzeugt" (§1) und die Kandidatenliste (§6) gelten damit nicht mehr. Kitten TTS 2 bleibt als lokale Rückfallebene (Worker vorhanden, Klon über Referenz-WAV plus `ref.txt`).
- **Folgen der Cloud:** Jeder Sprechtext geht an Fish; die Terms erlauben Fish, Inhalte zur Verbesserung der Modelle zu nutzen. Kostenlose Nutzung gilt nur für persönliche, nicht-kommerzielle Nutzung. Ratenlimits und Preise sind ungeklärt und werden vor dem Vollauf mit einer Stichprobe gemessen. Der API-Key liegt nur in der Umgebungsvariable `FISH_API_KEY`, nie im Repo.
- **Stimmen-Pool (§6):** Der Pool besteht zunächst aus den offiziellen Fish-Stimmen (Fish-Modell-ID statt `ref.wav`). Die Zuordnung Stimme -> Figur steht in `casting/casting.yaml`.
- **Emotionen (§7):** Für Fish werden Emotionen als Klammer-Anweisung am Satzanfang geschrieben (`[angry]`, `[sad]`, `[very excited]`), Laute als `[sighing]`, `[laughing]`, `[break]`. Fish-Cues sind englisch, freie Beschreibungen sind erlaubt. Für Kitten gilt: nur Emotions-Prefix und Betonung, keine Laut-Tags (werden vorgelesen).
- **Engine-Worker (§6):** Der Worker `fish` spricht HTTP statt eines lokalen Modells, nutzt aber dasselbe JSON-Lines-Protokoll. Der Cache-Schlüssel enthält den Modellnamen als Header-Wert.
- **Plan-1-Ergebnisse, die Plan 2 voraussetzt:** `drova_voice` (`loc`, `speech_text`, `emotions`, `render`, `bakeoff`, `engines`) und `DrovaVoice.Core` (`LineIds`) sind fertig und getestet; die Mod lädt in MelonLoader 0.7.3 mit Drova Modding API 0.5.4 und gibt `Core ok: 950774fdbc26dddf.ogg` aus (M0).
