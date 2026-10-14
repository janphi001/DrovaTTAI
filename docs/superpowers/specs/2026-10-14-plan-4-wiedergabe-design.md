# Plan 4: Wiedergabe in der Mod (Design)

Stand: 2026-10-14 · Status: vom Nutzer im Chat freigegeben (Umfang, Ansatz A, Regler per `MelonPreferences`). Ergänzt Spec §9 der Hauptspec (`2026-10-10-drova-voice-design.md`); wo beide abweichen, gilt dieses Dokument.

## 1. Ziel und Umfang

**Ziel:** Adela und Jero sind im Spiel hörbar. Die Einträge aus `Mods/DrovaVoice/Audio/de/index.json` (Vertrag: `docs/audio-format.md`) laufen synchron zu den Untertiteln, für NPC-Aussagen und Spieler-Auswahloptionen. Das ist der Rest von M3.

**Im Umfang:** Laden bei Bedarf, begrenzter Cache, stumm bei Fehlern, Lautstärkeregler Dialog und Spieler mit Boost bis 200 %, Ein/Aus, Einstellungen per `MelonPreferences`.

**Nicht im Umfang:** Namensvarianten (`#arden`/`#neutral`) und Spielerstimm-Sets (M5), Barks und ihre Entfernungslogik (M6), Briefe (M7), Menü oder Hotkeys für die Regler (später; Werte gelten erst nach Neustart), Hintergrund-Vorladen (nur wenn die Messung Ruckler zeigt).

## 2. Befunde zur Modding API 0.5.4 (per IL gelesen)

1. Das Abspielen macht das Spiel: es spielt `statement.audio` (`AudioClip`) über `DS_DialogueUGUI.localSource`. `DefaultAudioHandler` tippt nur die Untertitel passend zur Cliplänge.
2. `DefaultDialogueAudioConnector.OnDialogueTreeLoaded` lädt beim Baumladen alle Clips des Baums und blockiert den Hauptthread (`MainThreadDispatcher.WaitForTasks`). Das ist für große Figuren (Jero: 234 Zeilen) ungeeignet.
3. `DS_StatementNodePatch.Prefix` ruft `IAudioConnector.OnWorldDialogueStatement` bei jeder Aussage, **nur wenn `statement.audio == null`**. Lässt man den Clip beim Baumladen weg, kommt der Aufruf pro Zeile (das ist das Laden bei Bedarf).
4. `AudioManager.ReplaceDialogueAudioConnector(IAudioConnector)` und `ReplaceAudioHandler(IAudioHandler)` tauschen die Bausteine. Der Baumname, der Loca-Pfad (`useGlobalLoca ? statement.GlobalLocaPath : tree.LocaPath`), der Schlüssel (`statement.locaKey`) und der Aktorname stehen am Knoten zur Verfügung; das entspricht den Teilen der Zeilen-ID.
5. `DS_MultipleChoiceNodePatch.Prefix` (auf `OnOptionSelected`) spielt die Option nur dann mit Ton, wenn `choice.statement.audio` schon gesetzt ist. `IAudioHandler.HandleMultipleChoiceRequest` ist leer und wird nirgends aufgerufen. Die Optionsclips müssen wir also selbst laden, bevor der Spieler wählt.
6. `DialogueAudioDistanceManager` regelt `AudioSource.volume` nach Entfernung. Ein Gain auf den Samples bleibt davon unberührt.
7. `FileAudioProvider.LoadOggAudioAsync` ist die Vorlage: `VorbisReader` (NVorbis) liest alle Samples, `AudioClip.Create(name, samples/ch, ch, rate, false)` plus `SetData` laufen auf dem Hauptthread. `NVorbis.dll` liegt schon in `UserLibs`.
8. **`AudioManager` ist im Hauptmenü nicht initialisierbar.** Sein statischer Konstruktor erzeugt `new AssetBundleAudioProvider()`, dessen Konstruktor `WorldEventSystemManager.Instance.AreaNameSystem` liest; im Hauptmenü ist `Instance` noch `null`. Das ist die `TypeInitializationException` aus dem Export, und ein fehlgeschlagener statischer Konstruktor bleibt für die ganze Sitzung kaputt. Die Mod darf `AudioManager` deshalb erst berühren, wenn `Instance` existiert.

## 3. Architektur

```
DrovaVoice.Core (net6.0, ohne Il2Cpp, xUnit)
├─ AudioIndex      index.json lesen, validieren, Lookup(id) -> IndexEntry(file, duration, category)
├─ VoiceCategory    Dialog | Player (aus dem Dateipfad: "player/" -> Player, sonst Dialog)
├─ Gain            Prozent -> Faktor, Anwendung auf float[] mit weichem Begrenzer
├─ ClipBudget      LRU nach Bytes; die jüngsten N Einträge sind unverdrängbar
├─ VoiceSettings   Enabled, DialogPercent, PlayerPercent, CacheMegabytes (gültige Bereiche)
└─ OnceLog         "jede ID nur einmal loggen"

DrovaVoice (Il2Cpp-Schicht, dünn)
├─ Playback/VoiceConnector   IAudioConnector: OnDialogueTreeLoaded = No-op,
│                            OnWorldDialogueStatement = ID bilden, laden, statement.audio setzen
├─ Playback/ClipLoader       NVorbis -> float[] -> Gain -> AudioClip; 500-ms-Grenze; fängt alles ab
├─ Playback/ChoiceHook       Harmony-Postfix am Auswahlknoten: Optionsclips (ID "|c<index>") laden
├─ Playback/ClipStore        ClipBudget + Dictionary<id, AudioClip>; verdrängte Clips werden zerstört
└─ DrovaVoiceMod             Einstellungen lesen, Index laden, Connector ersetzen, Hook installieren
```

Regel: Was ohne Spiel prüfbar ist, liegt in `Core`. Die Il2Cpp-Schicht enthält nur Verkabelung und wird im Spiel abgenommen.

## 4. Ablauf einer Zeile

1. Das Spiel führt eine Aussage aus; der API-Prefix ruft `OnWorldDialogueStatement(node)`, weil `audio == null`.
2. Der Connector bildet `LineIds.Statement(tree.name, locaPath, locaKey)` (Loca-Pfad wie oben unter 2.4) und fragt `AudioIndex.Lookup`. Kein Eintrag: nichts tun (stumm, Untertitel wie im Original).
3. Ein Eintrag: `ClipStore` liefert den Clip oder `ClipLoader` erzeugt ihn (Gain nach Kategorie) und legt ihn ab. Fehler oder mehr als 500 ms: stumm, ID einmal loggen.
4. Der Connector setzt `node.statement.audio`. Das Spiel spielt ihn ab und die Untertitel laufen synchron.
5. Auswahlknoten: der Postfix geht über `availableChoices`, bildet `LineIds.Choice(..., index)` und setzt bei jeder Option mit Eintrag `choice.statement.audio` (Kategorie `player`).
6. Zeilen mit `$GVAR:` im Text haben keinen Eintrag im Index und bleiben stumm (bereits so im Vertrag).

## 5. Lautstärke

- Gain wird beim Dekodieren auf die Samples angewendet (nicht über `AudioSource.volume`): `Faktor = Prozent / 100`. Über 100 % wird weich begrenzt (Ziel: keine harte Übersteuerung bei 200 %); unter 100 % linear.
- Die Dateien sind −16 LUFS; wie laut das im Spiel wirkt, beurteilt der Nutzer mit den Reglern.
- Ein Clip enthält den Gain zum Ladezeitpunkt. Weil Werte nur beim Start gelesen werden, ist das konsistent.

## 6. Einstellungen (`MelonPreferences`, Kategorie `DrovaVoice`)

| Schlüssel | Standard | Bereich | Bedeutung |
|---|---|---|---|
| `Enabled` | `true` | — | Vertonung an/aus (aus: Standardconnector bleibt) |
| `DialogVolume` | `100` | 0–200 | NPC-Stimmen in Prozent |
| `PlayerVolume` | `100` | 0–200 | Spielerzeilen in Prozent |
| `AudioLanguage` | `de` | — | Unterordner unter `Audio/` |
| `CacheMB` | `64` | 8–512 | Obergrenze für geladene Clips |
| `Diagnostics` | `false` | — | Jede Zeile einmal loggen (geladen / ohne Eintrag), für die Abnahme |

Ungültige Werte werden auf den Bereich begrenzt und einmal geloggt.

## 7. Fehlerverhalten

- Fehlende oder defekte Datei: stumm, ID einmal geloggt.
- Index fehlt, Version ≠ 1 oder Sprache passt nicht: Warnung, der Standardconnector bleibt aktiv (Spiel unverändert).
- Jede Ausnahme in Hooks wird abgefangen; die Mod darf das Spiel nie anhalten.
- Verdrängter Clip wird mit `Object.Destroy` zerstört. Das Spiel sieht danach `audio == null` und der Prefix ruft beim nächsten Ausführen erneut den Connector. Die jüngsten Clips (Standard 8) werden nie verdrängt, damit kein laufender Clip zerstört wird.

## 8. Phasen und Abnahme

| Phase | Inhalt | Abnahme |
|---|---|---|
| 0 | Messung im Spiel (nur Logging, `Playback/Probe`) | Log zeigt: Connector-Ersatz greift trotz API-Initialisierung; `OnWorldDialogueStatement` feuert bei Adela; gebildete IDs finden sich im Index; Verhalten beim Überspringen/Schließen (R5); Methodenname des Auswahlknotens |
| 1 | Core + xUnit | Tests grün |
| 2 | Connector, ClipLoader, ClipStore, Installation | baut und deployt; Adelas erste Zeile hörbar |
| 3 | ChoiceHook | Spieleroptionen hörbar |
| 4 | Einstellungen, `docs/playback.md` | Regler wirken nach Neustart |
| 5 | Abnahme durch den Nutzer: Adela und Jero hörbar und synchron, Regler wirken | Urteil in `docs/decisions/` |

Phase 0 und 5 brauchen den Nutzer im Spiel; Phasen 1–4 sind ohne Spielstart baubar. Zeigt Phase 0, dass eine Annahme aus §2 nicht stimmt (z. B. der Ersatz des Connectors wird von der API überschrieben), wird die Spec angepasst, bevor Phase 2 beginnt.

## 9. Risiken

| # | Risiko | Gegenmaßnahme |
|---|---|---|
| P1 | `AudioManager` scheitert im Hauptmenü (siehe §2.8) | Connector erst in `OnUpdate` ersetzen, wenn `WorldEventSystemManager.Instance != null` (umgesetzt, `TryInstallConnector`) |
| P2 | Dekodieren auf dem Hauptthread ruckelt | 500-ms-Grenze; bei Messung Hintergrund-Vorladen der Folgezeilen |
| P3 | Loca-Pfad am Knoten weicht vom exportierten ab | Phase 0 vergleicht gebildete IDs mit dem Index; Export nutzt dieselbe Regel |
| P4 | Auswahlknoten-Methode heißt anders / ist anders erreichbar | Phase 0 ermittelt sie; Fallback: Laden im `DS_StatementNode`-Prefix des Folgeknotens |
| P5 | Clip wird beim Überspringen nicht gestoppt (R5) | In Phase 0 beobachten; ggf. `localSource.Stop()` am Handler |
