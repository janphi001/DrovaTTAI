# Handoff DrovaVoice (Stand 2026-10-15)

Zweck: Eine neue Sitzung soll damit ohne den alten Chatverlauf weiterarbeiten können. Zuerst lesen: dieses Dokument, dann `docs/decisions/` (neueste zuerst). Details je Thema stehen in den verlinkten Dokumenten, hier nur das, was man zum Einstieg braucht.

## Was ist das Projekt
KI-Stimmen für das Spiel **Drova – Forsaken Kin**. Ein Python-Generator (`generator/`, Befehl `drova-voice`) erzeugt aus dem Export des Spiels deutsche Sprachdateien (Fish Audio Cloud, Modell `s2.1-pro-free`); eine MelonLoader-Mod (`mod/`, C#) spielt sie im Spiel ab. Spiel: `D:\Games\Steam\steamapps\common\Drova - Forsaken Kin`. Nutzer: Jan, Antworten auf Deutsch.

## Stand
| Teil | Stand |
|---|---|
| Plan 1 Fundament, Plan 2 Fish + Export, Plan 3 Generator | fertig (Branches `plan-1-foundation`, `plan-2-fish-export`, `plan-3-generator`) |
| **Plan 4 Wiedergabe in der Mod** | **fertig und vom Nutzer abgenommen** (Branch `plan-4-playback`, aktuell; Notiz `docs/decisions/2026-10-playback-durchstich.md`) |
| Merge/Push der Branches | **nichts gepusht, nichts nach `main` gemerged**; Entscheidung beim Nutzer (siehe „Offene Entscheidungen“) |
| Tests | 151 xUnit (Core), 390 pytest (Generator), alle grün |

## Stimmen (Frage „wie viele?“)
- `casting/fish_voices.yaml`: **41 Stimmen** (22 männlich, 19 weiblich; bekannte Altersangaben: 12 jung, 14 mittel, 7 alt) **+ 7 Varianten** (Pitch/Formant/Tempo-Abwandlungen: alte Frau, alte Frau rau, Riese, Zwerg, Schurke hell, Jugendlicher, Knabe). Die Varianten sind nur in der Tabelle, **der Generator-Schritt dafür ist noch nicht gebaut**.
- Fehlende Typen: echte Kinderstimmen, alte Frauen (nur eine Stimme + Variante), helle Männerstimmen.
- In `casting/casting.yaml` zugeordnet sind **6 Sprecher**: Adela `melanie`, Jero `german_wisdom_m_3130ae`, Enya `lena`, Femke `schales_7ef3ea` (männlich), Gerion `lukas`, Gilwar `jonas`; `default_player: leon`. Alles vorläufig, der Nutzer entscheidet nach dem Hören. Insgesamt gibt es ~290 Sprecher im Spiel (Plan 5 soll alle besetzen).

## Was im Spiel hörbar ist
`Mods/DrovaVoice/Audio/de/index.json` hat **282 Einträge** (Zeilen der 6 besetzten Sprecher ohne Spieler-Auswahloptionen; Dateien OGG 48 kHz mono, −16 LUFS). Der Nutzer hat Enya, Femke, Gerion und Gilwar mit Emotionen gehört: „klingt gut“, Skip stoppt die Stimme, Lautstärke 100 % passt. Adela und Jero hat er im Spiel nie gefunden (Jero ist im Mittelspiel im Ruinenlager).

## Entscheidungen, die man nicht wieder aufrollen soll
- **Engine:** Fish Audio Cloud; Kitten nur lokale Rückfallebene (`docs/decisions/2026-10-tts-engine.md`). Texte gehen an Fish: **nur nach ausdrücklichem Ja des Nutzers**. Kosten/Tarif für den Vollauf ungeklärt (~13.000 Zeilen).
- **Spielerauswahl bleibt stumm** wie im Original (Spiel hat `saySelection` aus): Der Generator überspringt Antwortoptionen (`player_choice`, 6.491 Zeilen); nur 119 Aussagen des Spielers werden gesprochen (`docs/decisions/2026-10-player-choices-stumm.md`).
- **Regler** (Dialog, Spieler 0–200 %) vorerst nur per `UserData/MelonPreferences.cfg`, Wirkung nach Neustart; Menü/Hotkeys später.
- Emotionen: Regeln aus Regieanweisungen + Haiku-Markierung (Subagent schreibt `casting/emotions.jsonl`-Zeilen mit `source: llm`).

## Fallen (nicht im Code ersichtlich)
- **Export nur im Hauptmenü, Fenster vorn; danach Spiel beenden.** Ein Export im Hauptmenü macht die Vertonung der Sitzung wirkungslos: `AudioManager` der Modding API scheitert dort dauerhaft (`WorldEventSystemManager.Instance` ist null). Darum ersetzt die Mod den Connector erst in der Welt (`TryInstallConnector`).
- Die API ruft `OnWorldDialogueStatement` nur bei `statement.audio == null`; der Standardconnector lädt alle Clips eines Baums beim Baumladen und blockiert den Hauptthread (darum eigener Connector mit Laden bei Bedarf). `DefaultAudioHandler` spielt nichts ab, das Spiel spielt `statement.audio`.
- Mod bauen (`dotnet build mod/DrovaVoice -c Release`) **kopiert in den Spielordner** (Spiel muss geschlossen sein).
- Werkzeug-Eigenheit: In Python-Heredocs und mit dem Write-Werkzeug werden `\\`/`\n`-Folgen verändert; für Strings mit Rückstrich das Edit-Werkzeug nutzen. Pfadlisten, die Python unter Windows schreibt, haben `\r\n` (vor `rm`/Schleifen `tr -d '\r'`).
- Zum Lesen von Il2Cpp-/API-Typen diente ein Mono.Cecil-Wegwerfwerkzeug (nutzt `MelonLoader/net6/Mono.Cecil.dll`); liegt nur im Scratchpad der Sitzung, in 5 Minuten neu gebaut.

## Arbeitsregeln des Nutzers
- Antworten auf Deutsch. **Vor jedem Download/jeder Installation fragen** (Dateiname, Quelle, Größe); alles auf Laufwerk D:.
- **Keine echten Drova-Dialogtexte ins Git** (Tests mit erfundenem Text); Spieltexte nur nach Ja an Dienste.
- **Fish-Key (`FISH_API_KEY`) nie speichern**: Er kommt vom Nutzer im Chat und wird nur als Umgebungsvariable im Einzelbefehl benutzt. Er stand mehrfach im Chat → der Nutzer soll ihn bei Fish zurücksetzen.
- Gut abgegrenzte Aufgaben dürfen Haiku-Subagents erledigen; für Reviews mag der Nutzer lesende Opus-Subagents. Hörtests nimmt der Nutzer selbst ab.
- Commits englisch, Imperativ, mit `Co-Authored-By`-Zeile; nichts pushen oder mergen ohne Nachfrage.

## So macht man weiter (Generator)
Alle Befehle in `generator/` (siehe `docs/generator.md`): `extract` (aus `data/export/de/manifest-loaded.json`) → `cast --check --npc X` → `emote --npc X` → `synth --npc X` (Fish, 8 parallel, braucht Key + Ja) → `encode` → `install` → `report`/`preview`. Neue Sprecher: Stimme in `casting/casting.yaml` eintragen (`name: {voice: schlüssel}`).

## Offene Entscheidungen / nächste Schritte
1. **Plan 5 = Casting und Vollauf (M4)** (Empfehlung): alle ~290 Sprecher besetzen (Geschlecht per LLM schätzen, Nutzer korrigiert), Emotionen per Haiku für alle Zeilen, Varianten-Schritt, Kosten klären, dann Vollauf. Ablauf: Skill `superpowers:brainstorming` → Spec → `superpowers:writing-plans`.
2. Danach Mod-Ausbau: Namensvarianten `#arden`/`#neutral` (535 `$GVAR`-Zeilen, bisher übersprungen), Regler im Spiel, Barks (M6, braucht Entfernungslogik), Briefe (M7).
3. Offene Lücken: 98-%-Lücke im Export (1.181 Zeilen ohne Sprecher; Lösungsansatz in `docs/decisions/2026-10-export-findings.md`), Jero und Adela im Spiel noch nie gehört, Regler-Wirkung (z. B. 150 %) im Spiel nicht geprüft.
4. Git: `plan-4-playback` (auf `plan-3-generator` ← `plan-2-fish-export` ← `plan-1-foundation`) mergen oder PR; Historie umschreiben (Gmail-Adresse in ~58 Commits, Skript `.superpowers/rewrite-history.sh`); Lizenz wählen (Empfehlung MIT).

## Wo steht was
- Specs und Pläne: `docs/superpowers/specs/`, `docs/superpowers/plans/` (Plan 4: `2026-10-14-plan-4-wiedergabe*.md`).
- Befunde: `docs/decisions/*.md`; Vertrag Generator ↔ Mod: `docs/audio-format.md`; Mod-Bedienung und Fehlersuche: `docs/playback.md`; Export: `docs/export.md`.
- Gedächtnis (außerhalb des Repos): `C:\Users\jpmin\.claude\projects\D--Games-Projekte-DrovaTTAI\memory\` (`plan-1/2/4-status.md`).
