# Handoff: Bug „alte Dialoge spielen beim Herumlaufen ab“ (Stand 2026-10-15)

Für eine neue Sitzung ohne Chatverlauf. Zuerst lesen: `docs/HANDOFF.md` (Projekt, Regeln, Fallen), `docs/playback.md` (Wiedergabe in der Mod), `docs/decisions/2026-10-casting-vollauf.md` (was seit Plan 5 im Index steht). Antworten an den Nutzer auf Deutsch.

## Symptom (Nutzer, nach dem Anhören im Spiel)
Die Stimmen funktionieren „soweit ganz gut“. Aber: **Beim normalen Herumlaufen spielen zwischendurch Audio-Dialoge ab, die schon längst vorbei sind.** Genaueres weiß der Nutzer nicht (welche Zeilen, wie lange nach dem Gespräch, ob mit oder ohne Untertitel). Das ist als Erstes zu klären (siehe „Nächste Schritte“).

## Was neu ist (warum es erst jetzt auftritt)
Bis Plan 4 waren nur 6 Sprecher (282 Zeilen) im Index. Seit Plan 5 liegen **11.413 Einträge** im Spielordner (`Mods/DrovaVoice/Audio/de/index.json`, 506 MB): alle 245 benannten Sprecher. Darunter viele Bäume, die das Spiel **nicht als Gespräch mit Fenster** ausführt, sondern nebenbei in der Welt (Anzahl sprechbarer, benannter Dialogzeilen im Index nach Baumart): `Quest_` ~5.600, `Greet` ~1.140 (NPC grüßt beim Vorbeigehen), `Intent` ~1.000 (`DT_PreApo_Intent_*`), `Talk` ~260, `Reaction` ~80, `Cutscene` ~60, `WorldDialog*` ~20. Barks (`category: bark`) und generische Sprecher sind **nicht** im Index.

## Wie die Wiedergabe funktioniert (relevant für die Fehlersuche)
Details in `docs/playback.md`. Kurz:
- `mod/DrovaVoice/Playback/VoiceConnector.cs` ersetzt den Audio-Connector der Modding API (erst in der Welt). Die API ruft `OnWorldDialogueStatement(DS_StatementNode)` **nur, wenn `statement.audio == null`**. Der Connector sucht die Zeilen-ID im Index, dekodiert die OGG (NVorbis, `ClipLoader`/`OggDecoder`), setzt `statement.audio = clip`. **Abgespielt wird der Clip vom Spiel selbst**, nicht von der Mod. Die Mod startet und stoppt nichts.
- `ClipStore` hält Clips im Cache (64 MB, die 8 jüngsten werden nie verdrängt); verdrängte Clips werden zerstört.
- Wichtige Folge: **Ist `statement.audio` einmal gesetzt, bleibt der Clip am Knoten.** Führt das Spiel den Knoten später noch einmal aus (egal von welchem Mechanismus: Welt-Gespräch, Begrüßung, „Intent“, Wiederholung), spielt es den Clip ab, **ohne dass der Connector noch einmal aufgerufen wird**. Dann gibt es auch **keine Logzeile**: `Diagnostics` loggt nur beim Laden (`[Zeile] geladen: …`), nicht beim Abspielen.
- Das Spiel stoppt die Stimme bei Skip (Nutzer hat das getestet, ok). Ob es sie stoppt, wenn ein Gespräch von selbst endet (Entfernung, Abbruch, NPC verschwindet), ist **ungeprüft**.

## Beobachtungen aus dem Log (Sitzung 14:17–14:22, `Diagnostics = true`)
Kopie: `out/bug-stale-audio-Latest.log` (gitignored; Original wird beim nächsten Spielstart überschrieben). Auszug der Zeilen-IDs, die in der Sitzung geladen wurden: viele `DT_PreApo_Greet_1_NPC_*` (Swenn, Erwin, Lobo, Gilwar, Fia, Willi, Gerdwin, Palina), `DT_Quest_GuardTree_NPC_Niala`, `DT_PreApo_Intro_1_NPC_Lukan`, `DT_PreApo_1_NPC_Gerdwin|Dialogues/Global|OnlyNemetonTeaching`, `DT_PreApo_Intent_1_NPC_Palina`, `DT_Comment_Chest_…` (Spieler). Eine Zeile **ohne Eintrag**: `DT_WorldDialogue_Template|RestWorldDialogue|TalkToMombert_93` (Welt-Gespräch, nicht vertont, wie vorgesehen). Die Greet-Zeilen (`Hey5`, `Plh_4` …) laufen kurz (0,3 bis 3,7 s) und kommen auch dann, wenn der Nutzer nur an NPCs vorbeiläuft. **Das Log zeigt keine eindeutig „alte“ Zeile**, weil Abspielen nicht geloggt wird.

## Hypothesen (nach Wahrscheinlichkeit; alle ungeprüft)
1. **Welt-/Begrüßungs-/Intent-Bäume werden vom Spiel nebenbei oder wiederholt ausgeführt**, und das Spiel spielt `statement.audio` dabei ab, auch wenn kein Gespräch (Fenster) mehr läuft. Im Original war `audio` immer null, deshalb fiel das nie auf. Die Mod hängt jetzt Clips an Knoten, die das Spiel anders benutzt als erwartet.
2. **Das Gespräch endet (Entfernung, Abbruch), der Clip läuft aber weiter**, weil das Spiel nur beim Skip stoppt, nicht beim stillen Ende.
3. **Der Clip bleibt am Knoten und wird bei einer späteren Ausführung desselben Baums erneut gespielt** (z. B. beim erneuten Begegnen, beim Laden eines Spielstands, beim Wiederholen von „Intent“/„Greet“).
4. **Cache-Effekt:** `ClipStore` zerstört verdrängte Clips; ein noch referenzierter/abspielender Clip könnte falsch oder mit anderem Inhalt weiterlaufen (unwahrscheinlicher, weil der Cache nach `statement.audio == null` neu lädt; trotzdem prüfen, ob ein zerstörter Clip an einem Knoten hängen bleibt).

## Nächste Schritte
1. **Nutzer fragen** (kurz): Wann tritt es auf (Stadt/Lager, bei bestimmten NPCs, nach einem Gespräch)? Mit Untertiteln oder ohne? Stimme des NPCs oder eines anderen? Wiederholt es sich an derselben Stelle? Ein Hinweis wie „bei Nemeton, nach Gespräch mit X“ genügt.
2. **Abspielen sichtbar machen** (Mod, `Diagnostics`): Beim Zuweisen des Clips die Zeilen-ID am Clip merken (z. B. Clipname = ID) und per Harmony-Postfix auf die Stelle loggen, an der das Spiel `statement.audio` abspielt (AudioSource/`PlayOneShot` im Dialog-/Statement-Code der Modding API oder des Spiels; mit dem Mono.Cecil-Wegwerfwerkzeug nachsehen, siehe `docs/HANDOFF.md`, Abschnitt Fallen). Alternativ: im Spiel `Diagnostics = true`, der Nutzer notiert die Uhrzeit, wann es auftritt, und man gleicht mit dem Log ab (nur Ladezeilen, wenig Aussagekraft).
3. **Mit dem Log die Baumart ermitteln**, die die fremden Stimmen auslöst. IDs nach Text nachschlagen: `data/lines.jsonl` (Feld `id`, `tree`, `speech`; gitignored, enthält Spieltext, nicht committen).
4. **Entscheiden:**
   - *Schnell, ohne Mod-Änderung:* die verdächtige Baumart aus dem Index nehmen. Der Generator überspringt Gründe über `skip` in `drova_voice/lines.py` (z. B. neuer Grund für `Greet`/`Intent`/Welt-Bäume) oder man löscht die IDs aus `Mods/DrovaVoice/Audio/de/index.json` (`install` mit `drop_ids`). Kosten: diese Zeilen sind dann stumm.
   - *Sauber, Mod-Änderung:* Clip nur setzen, wenn der Knoten wirklich im Gesprächsfenster läuft, und `statement.audio` nach dem Gespräch wieder auf null setzen (und laufende AudioSources stoppen), damit der Connector bei der nächsten Ausführung neu entscheiden kann.
5. Nach jeder Mod-Änderung: `dotnet build mod/DrovaVoice -c Release` (**kopiert in den Spielordner, Spiel muss geschlossen sein**), Nutzer testet im Spiel (er nimmt Hörtests selbst ab).

## Stand des Repos
- Branch `plan-5-casting` (auf `plan-4-playback`), **nichts gepusht, nichts gemerged**. Mod-Code liegt in `mod/DrovaVoice` und `mod/DrovaVoice.Core` (xUnit 151 Tests). Generator-Tests: 471 pytest (`cd generator && .venv/Scripts/python -m pytest -q`).
- Spielordner: `D:\Games\Steam\steamapps\common\Drova - Forsaken Kin`; Log `MelonLoader/Latest.log`; Einstellungen `UserData/MelonPreferences.cfg` (`Diagnostics = true` ist bereits gesetzt).
- Der Nutzer will Spieltexte nicht ins Git; Fish-Key nie speichern; vor Downloads/Installationen fragen (siehe `docs/HANDOFF.md`, Arbeitsregeln).
