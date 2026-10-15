# Barks: Welt-Kommentare und generische Sprecher (Design)

Stand 2026-10-15. Baut auf Plan 4 (Wiedergabe), Plan 5 (Casting, Vollauf) und den Namensvarianten auf. Meilenstein M6 der Haupt-Spec (§9). Vertrag: `docs/audio-format.md`.

## Ziel
Wer durch die Welt läuft, hört NPCs im Vorbeigehen Sprüche (Welt-Kommentare, Kampfrufe) und Zeilen von „namenlosen“ Figuren in passenden Stimmen. Diese Sprüche haben einen eigenen Regler und werden mit der Entfernung leiser. **Dieselbe Figur klingt immer gleich** (Entscheidung des Nutzers: Ansatz B, „feste Stimme pro Figur“). Wo die Figur zur Laufzeit nicht bestimmbar ist, greift Ansatz A als Rückfall: eine Stimme je Zeile aus einem Pool, deterministisch nach Zeilen-ID.

## Umfang (Stand `data/lines.jsonl`, 19.535 Zeilen)
| Gruppe | Zeilen | Behandlung |
|---|---|---|
| Barks benannter Sprecher (`category=bark`, Sprecher im Casting) | 175, davon 171 sprechbar (4 `unspeakable` bleiben stumm), 5.425 Zeichen | normale Besetzung aus `casting.yaml`/`casting_auto.yaml`; kein Pool nötig |
| Barks generischer Sprecher (`NPC`) | 152, 4.061 Zeichen | Stimmenpool (B/A) |
| Dialogzeilen generischer Sprecher (`NPC`, Teacher, Druid, Actor, Participant) | 208, davon 205 sprechbar (2 `gvar_name`, 1 `unspeakable` bleiben stumm), 9.567 Zeichen | Stimmenpool (B/A) |
| gesamt neu zu vertonen | 171 benannte + 357 Pool-Zeilen (13.628 Zeichen) | |

Nicht im Umfang: Briefe (M7), Spielerstimm-Sets, Regler im Spielmenü (Werte weiter per `MelonPreferences.cfg`), Kinderstimmen, Namensvarianten für Pool-Zeilen (gibt es dort nicht; bei Bedarf gilt die vorhandene neutrale Regel).

## Befunde (nur Lesen der Spiel-DLLs; im laufenden Spiel noch nicht bestätigt)
- Der API-Patch `DS_StatementNodePatch.Prefix` ruft `OnWorldDialogueStatement` für jede Aussage ohne Audio, auch für Welt-Kommentare. Bei dem Aufruf liest er `statementNode.finalActor` (`DS_DialogueActor`). Damit erreicht auch unser `VoiceConnector` die sprechende Figur.
- `DS_DialogueActor` bietet `Actor`, `name`, `transform`, `GetActorGender()` (`ActorBodyType.BodyType`: `None`/`Strong`/`Petite`) und `GetEntityInfo()`. Der `Actor` hat ein `GuidComponent` (`GuidString`) und `GetEntityInfo()` (lokalisierter Name, `GetLocaKey()`).
- Die Entfernungslogik besteht in der API schon: `DialogueAudioDistanceManager.Register(AudioSource, Transform)` wird vom `DSDialogueUGUIPatch.Postfix` für Dialogblasen aufgerufen (Min-/Max-Entfernung, Glättung). Ob Barks diesen Weg nehmen und ob unsere Lautstärke dort erhalten bleibt, ist offen (R2 der Haupt-Spec).
- Unbekannt: ob die `GuidString` eines Welt-NPCs über Sitzungen stabil ist, ob `Strong`/`Petite` verlässlich männlich/weiblich bedeutet und ob generische Sprecher einzelne Figuren sind (und nicht eine Spawn-Vorlage mit gleicher GUID).

## Stufe 0: Laufzeit-Probe (zuerst, entscheidet über B)
Eine kurze Probe in `OnWorldDialogueStatement` (nur Logzeile, keine Wiedergabe) protokolliert je Aussage: Sprecher-Name der Zeile, `finalActor.name`, `GetActorGender()`, `GuidString`, `EntityInfo`-Locakey, Entfernung zur Kamera. Der Nutzer läuft damit durch eine Stadt, ein Lager und einen Kampf (mit Spielstart, Neustart, erneutem Laden).

Entscheidungsregeln:
- **Schlüssel stabil** (gleiche Figur, gleicher Schlüssel nach Neustart, verschiedene Figuren verschiedene Schlüssel) → B mit diesem Schlüssel.
- **Schlüssel unbrauchbar, Geschlecht lesbar** → B nur nach Geschlecht (kein Figurbezug), Stimme je Zeile aus dem Geschlechtspool (= A mit Geschlecht).
- **Weder noch** → A ohne Geschlecht, Pool aus beiden Geschlechtern.
Die übrigen Stufen ändern sich dadurch nicht, nur die Schlüsselwahl in der Mod.

## Generator
- **Pools:** `casting/pools.yaml` definiert je Geschlecht (`m`, `w`) eine kleine Liste vorhandener Stimmen oder Varianten aus `fish_voices.yaml` (Richtwert 3 bis 4 je Geschlecht, keine Stimmen, die schon einem benannten Sprecher mit vielen Zeilen gehören). Ein Alters- oder Typmix (alt, jung) ist erlaubt; Kinder entfallen.
- **Zeilenbildung:** Pool-Zeilen (`generic` = wahr, nicht `skip`) bekommen keine einzelne Stimme, sondern je Poolstimme einen Auftrag. Die ID bleibt die Basis-ID; die Poolstimme steht als Variante `#v<Poolschlüssel>` (z. B. `…#vm1`), wie schon `#neutral` (`ids.with_variant`).
- **Mengenbegrenzung:** Pool-Zeilen × Poolgröße = 357 × 7 ≈ 2.500 Clips, ca. 95.000 Zeichen (rund ein Neuntel des Vollaufs mit 858.000 Zeichen). Ablauf wie bisher: `synth` nur nach ausdrücklichem Ja des Nutzers, Schlüssel kommt vom Nutzer im Einzelbefehl. Auf Wunsch zuerst nur die 152 generischen Barks (ca. 1.060 Clips, 28.000 Zeichen).
- **Benannte Barks** laufen wie normale Dialogzeilen über `cast`/`emote`/`synth` mit der bestehenden Besetzung. Die 166 Bark-WAV im Cache `cache/synth/` (versehentlich erzeugt) werden wiederverwendet, soweit Text und Stimme zu den Zeilen passen; der `synth`-Cache entscheidet dies über den Zeilen-Hash.
- **Kategorie im Index:** `encode`/`install` legen Barks nach `bark/<sha1(id#variante)[:16]>.ogg` (Ordner im Vertrag schon vorgesehen), Dialogzeilen generischer Sprecher bleiben in `dialog/`. Der `category`-Wert im Eintrag bestimmt, welcher Regler gilt.
- **Emotionen:** `emote` ist für Barks mit Regeln und Haiku-Markierung wie bisher; Barks sind kurz, Regelfälle genügen (Kampfrufe: Wut/Schmerz aus Regieanweisung).
- **Bericht:** `report --by-speaker` führt „Pool (m/w)“ als eigene Zeilen, damit Lücken sichtbar sind.

## Mod
- **Indexvertrag:** Der Index führt je Basis-ID die Poolvarianten im Block `variants` (z. B. `["vm1","vm2","vm3","vw1","vw2","vw3"]`). Das gibt es für `neutral` bereits; `AudioIndex` muss die Liste bereitstellen (bisher nicht gelesen).
- **Figur → Stimme:** Neue Core-Funktion `PoolVoice.Pick(variants, gender, figureKey, lineId)`: filtert nach Geschlecht (Präfix `m`/`w`; ohne Geschlecht alle), bildet `hash(figureKey) mod n` (B) oder, wenn kein Schlüssel vorliegt, `hash(lineId) mod n` (A). Der Hash ist ein fester FNV-1a, damit die Wahl über Sitzungen und Plattformen stabil ist und ohne Spiel testbar bleibt. Gibt es die gewählte Variante für diese Zeile nicht, wird die nächste im Ring genommen; gibt es keine Variante, bleibt die Zeile stumm.
- **Verbindung:** `VoiceConnector.OnWorldDialogueStatement` liest `statementNode.finalActor` (`GetActorGender`, `GuidString` bzw. der in Stufe 0 gewählte Schlüssel), alles in try/catch. Eine Figur, die sich nicht auslesen lässt, ergibt A, nie einen Abbruch. Der bisherige Ablauf für benannte Sprecher bleibt unverändert und hat Vorrang (Index-Nachschlag Basis-ID zuerst; nur wenn der Eintrag fehlt und Poolvarianten existieren, gilt die Pool-Auswahl).
- **Lautstärke:** `VoiceSettings` bekommt `BarkVolume` (Standard 100, 0 bis 200, wie `DialogVolume`); `PercentFor(entry.Category)` wird um die Kategorie `bark` erweitert (im Plan zu prüfen, was `PercentFor` heute für unbekannte Kategorien zurückgibt).
- **Entfernung:** Zuerst prüfen (Stufe 1), ob Barks über `DialogueAudioDistanceManager` laufen und ob die Lautstärke ankommt. Wenn ja: nichts nachbauen, nur Lautstärkefaktor. Wenn nein: eigene Abschwächung für Bark-Quellen (lineare Dämpfung zwischen `BarkMinDistance` und `BarkMaxDistance`, Standard 4 und 20 Einheiten, einstellbar), umgesetzt als kleiner `MonoBehaviour` auf der Quelle des Clips. Das Ergebnis der Prüfung steht in `docs/decisions/`.
- **Fehlerverhalten:** unverändert (Spec §10): fehlende oder defekte Datei → stumm, Untertitel wie im Original; jede ID nur einmal im Log.

## Tests
- Python (erfundene Texte): Pool-Zeilen erzeugen je Poolstimme genau einen Auftrag mit `#v…`-ID; benannte Barks nicht; `install` schreibt `bark/`-Pfade und den Block `variants`; Bericht zählt Pool-Lücken.
- C# (xUnit, Core): `PoolVoice.Pick` ist deterministisch, gleiche Figur → gleiche Variante, verschiedene Zeilen derselben Figur → dieselbe Stimme, Geschlechtsfilter, Rückfall A ohne Schlüssel, Ring bei fehlender Variante, keine Variante → leer; FNV-1a mit festen Testvektoren (`tests/vectors`).
- Im Spiel nimmt der Nutzer ab: Barks hörbar, leiser mit Entfernung, `BarkVolume` wirkt, dieselbe Figur klingt nach Neustart gleich.

## Reihenfolge der Stufen
0. Laufzeit-Probe, danach Entscheidung über den Schlüssel (kleiner Mod-Build, Spiel geschlossen bauen).
1. Entfernungsprüfung im Spiel mit einem vorhandenen benannten Bark (ohne neues Audio möglich, etwa einem der 166 bereits erzeugten).
2. Generator: Pools, Zeilenbildung, Bericht (Tests grün, kein Fish-Aufruf).
3. Vertonung der benannten Barks, dann der Pool-Zeilen (Fish nur nach Ja des Nutzers).
4. Mod: `PoolVoice`, Connector, `BarkVolume`, Entfernung bei Bedarf.
5. Hörtest und Dokumentation (`audio-format.md`, `playback.md`, `generator.md`, `HANDOFF.md`).

## Risiken
- **Schlüssel instabil:** dann gilt nur A, ein Figurbezug entfällt; das ist ausdrücklich der Rückfall und kein Fehler.
- **Gleiche GUID für mehrere Figuren** (Spawn-Vorlage): mehrere Figuren teilen eine Stimme. Die Probe zeigt es; Abhilfe wäre die Mischung aus GUID und Positions- oder Spawn-Hinweis, falls verfügbar, sonst A.
- **Geschlecht und Körpertyp** sind nicht dasselbe; weicht `Strong`/`Petite` vom hörbaren Geschlecht ab, entscheidet der Nutzer in der Probe, ob es nur nach Geschlecht des NPC-Namens (`npcs.json`) oder gar nicht gefiltert wird.
- **Kosten:** unter Fish ungeklärt wie beim Vollauf; Pool klein halten, erst Barks, dann Dialogzeilen.
- **Rechtliches:** Texte gehen an Fish nur nach ausdrücklichem Ja; keine echten Spieltexte ins Git.
