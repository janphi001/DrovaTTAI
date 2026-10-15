# Handoff DrovaVoice (Stand 2026-10-15)

Zweck: Eine neue Sitzung soll damit ohne den alten Chatverlauf weiterarbeiten können. Zuerst lesen: dieses Dokument, dann `docs/decisions/` (neueste zuerst). Details je Thema stehen in den verlinkten Dokumenten, hier nur das, was man zum Einstieg braucht.

## Was ist das Projekt
KI-Stimmen für das Spiel **Drova – Forsaken Kin**. Ein Python-Generator (`generator/`, Befehl `drova-voice`) erzeugt aus dem Export des Spiels deutsche Sprachdateien (Fish Audio Cloud, Modell `s2.1-pro-free`); eine MelonLoader-Mod (`mod/`, C#) spielt sie im Spiel ab. Spiel: `D:\Games\Steam\steamapps\common\Drova - Forsaken Kin`. Nutzer: Jan, Antworten auf Deutsch.

## Stand
| Teil | Stand |
|---|---|
| Plan 1 Fundament, Plan 2 Fish + Export, Plan 3 Generator | fertig (Branches `plan-1-foundation`, `plan-2-fish-export`, `plan-3-generator`) |
| **Plan 4 Wiedergabe in der Mod** | **fertig und vom Nutzer abgenommen** (Branch `plan-4-playback`; Notiz `docs/decisions/2026-10-playback-durchstich.md`) |
| **Plan 5 Casting und Vollauf** | **Code fertig, Vollauf bei Fish durch** (Branch `plan-5-casting` auf `plan-4-playback`; 471 pytest grün; alle 245 benannten Sprecher besetzt und vertont, `report --by-speaker`: Lücken 0; Notiz `docs/decisions/2026-10-casting-vollauf.md`). Stichprobe im Spiel vom Nutzer abgenommen (2026-10-15) |
| Merge/Push der Branches | erledigt: `main` und `origin/main` stehen auf `plan-5-casting` (gepusht) |
| Tests | 151 xUnit (Core), 471 pytest (Generator), alle grün |

## Stimmen (Frage „wie viele?“)
- `casting/fish_voices.yaml`: **41 Stimmen** (22 männlich, 19 weiblich; bekannte Altersangaben: 12 jung, 14 mittel, 7 alt) **+ 7 Varianten** (Pitch/Formant/Tempo-Abwandlungen: alte Frau, alte Frau rau, Riese, Zwerg, Schurke hell, Jugendlicher, Knabe). Seit Plan 5 setzt `encode` das Rezept (ffmpeg `rubberband`) auf die Basisstimme an; in `casting.yaml` darf `voice:` ein Variantenschlüssel sein.
- **Besetzung (Plan 5):** 245 Sprecher, `casting/casting_auto.yaml` (erzeugt, `cast --propose`; seither bleibt sie bei Wiederholung stehen, `--reset` verwirft sie) unter `casting/casting.yaml` (von Hand, gewinnt; u. a. die 6 früheren Sprecher, Jola, Meluna, Reija). Steckbriefe: `casting/profiles.jsonl`.
- Fehlende Typen: echte Kinderstimmen, alte Frauen (nur eine Stimme + Variante), helle Männerstimmen.
- Ältere Besetzung der 6 Sprecher (Adela `melanie`, Jero `german_wisdom_m_3130ae`, Enya `lena`, Femke `schales_7ef3ea` männlich, Gerion `lukas`, Gilwar `jonas`; `default_player: leon`) steht weiter in `casting.yaml` und gewinnt gegen die Auto-Zuteilung.

## Was im Spiel hörbar ist
`Mods/DrovaVoice/Audio/de/index.json` hat **11.413 Einträge** (alle 245 benannten Sprecher und die Aussagen des Spielers, ohne Auswahloptionen; 506 MB, OGG 48 kHz mono, −16 LUFS). Der Nutzer hat vor dem Vollauf Enya, Femke, Gerion und Gilwar gehört („klingt gut“, Skip stoppt die Stimme, Lautstärke 100 % passt); die Stichprobe im Spiel nach dem Vollauf steht aus.

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
- Commits englisch, Imperativ, **ohne** `Co-Authored-By`- oder sonstige Claude-Zeile (Nutzer will nicht als Mitautor stehen); nichts pushen oder mergen ohne Nachfrage.

## So macht man weiter (Generator)
Alle Befehle in `generator/` (siehe `docs/generator.md`): `extract` (aus `data/export/de/manifest-loaded.json`) → `cast --check --npc X` → `emote --npc X` → `synth --npc X` (Fish, 8 parallel, braucht Key + Ja) → `encode` → `install` → `report`/`preview`. Neue Sprecher: Stimme in `casting/casting.yaml` eintragen (`name: {voice: schlüssel}`).

## Offene Entscheidungen / nächste Schritte
0. Bug "alte Dialoge beim Herumlaufen" ist behoben und abgenommen (`docs/HANDOFF-bug-stale-audio.md`).
1. **Stichprobe im Spiel: erledigt und abgenommen (2026-10-15), keine Korrekturen nötig.** Plan 5 ist damit abgeschlossen. Ursprünglich vorgesehen: (Spiel starten, mit verschiedenen NPCs sprechen; Alte-Frau-, Riesen- und Kinderstimmen besonders), danach Korrekturen in `casting/casting.yaml` und die betroffenen Zeilen neu erzeugen (WAV in `cache/synth/` löschen, `synth --npc X`, `encode`, `install`). Plan 5 ist sonst abgeschlossen.
2. Danach Mod-Ausbau: Namensvarianten `#arden`/`#neutral` (535 `$GVAR`-Zeilen, bisher übersprungen), Regler im Spiel, Barks (M6, braucht Entfernungslogik), Briefe (M7).
3. Offene Lücken: 98-%-Lücke im Export (1.181 Zeilen ohne Sprecher; Lösungsansatz in `docs/decisions/2026-10-export-findings.md`), Jero und Adela im Spiel noch nie gehört, Regler-Wirkung (z. B. 150 %) im Spiel nicht geprüft.
4. Git: erledigt (2026-10-15). Historie umgeschrieben (Autor GitHub-noreply), Backup-Branches und `refs/original` gelöscht, `main` = `plan-5-casting` = `origin/main`, gepusht; MIT-Lizenz und README da.

## Wo steht was
- Specs und Pläne: `docs/superpowers/specs/`, `docs/superpowers/plans/` (Plan 4: `2026-10-14-plan-4-wiedergabe*.md`).
- Befunde: `docs/decisions/*.md`; Vertrag Generator ↔ Mod: `docs/audio-format.md`; Mod-Bedienung und Fehlersuche: `docs/playback.md`; Export: `docs/export.md`.
- Gedächtnis (außerhalb des Repos): `C:\Users\jpmin\.claude\projects\D--Games-Projekte-DrovaTTAI\memory\` (`plan-1/2/4-status.md`).
