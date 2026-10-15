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
| Namensvarianten | neutral, siehe docs/superpowers/specs/2026-10-15-namensvarianten-design.md; Code fertig, nach `main` gemergt und gepusht (Branch `plan-6-namensvarianten`); 94 neutrale Zeilen bei Fish erzeugt, installiert (Index 11.507 Einträge) und Mod gebaut (2026-10-15); Hörtest im Spiel steht aus. Die 166 dabei versehentlich miterzeugten Bark-Zeilen wurden in Plan 7 wiederverwendet |
| **Plan 7 Barks und Stimmenpool** | Code, Doku und Bark-Vertonung fertig, im Spiel abgenommen (Stimmen nach Geschlecht stimmig, Entfernungsregelung 15–120 „viel besser“); Branch `plan-7-barks`, nach `main` gemergt und gepusht. Spec `docs/superpowers/specs/2026-10-15-barks-design.md`, Plan `docs/superpowers/plans/2026-10-15-plan-7-barks.md`. Die 205 generischen Dialogzeilen (Pool) sind ebenfalls vertont (1.230 Clips, 2026-10-15); im Spiel noch nicht gehört |
| **Plan 8 Regler im Optionsmenü** | Panel „Drova Voice“ im Optionsmenü des Spiels (Schalter, Dialog/Spieler/Barks 0–200 %, Bark-Reichweite), wirkt ohne Neustart; im Spiel abgenommen (Lautstärken, Aus, Neustart), nach `main` gemergt. Spec `docs/superpowers/specs/2026-10-15-optionsmenue-design.md`, Plan `docs/superpowers/plans/2026-10-15-plan-8-optionsmenue.md`; Verhalten: `docs/playback.md` (Optionsmenü) |
| Merge/Push der Branches | erledigt (2026-10-15): Pläne 1 bis 7 sind in `main` gemergt, `main` = `origin/main`; die Plan-Branches bestehen lokal weiter |
| Tests | 201 xUnit (Core), 496 pytest (Generator), alle grün |

## Stimmen (Frage „wie viele?“)
- `casting/fish_voices.yaml`: **41 Stimmen** (22 männlich, 19 weiblich; bekannte Altersangaben: 12 jung, 14 mittel, 7 alt) **+ 7 Varianten** (Pitch/Formant/Tempo-Abwandlungen: alte Frau, alte Frau rau, Riese, Zwerg, Schurke hell, Jugendlicher, Knabe). Seit Plan 5 setzt `encode` das Rezept (ffmpeg `rubberband`) auf die Basisstimme an; in `casting.yaml` darf `voice:` ein Variantenschlüssel sein.
- **Besetzung (Plan 5):** 245 Sprecher, `casting/casting_auto.yaml` (erzeugt, `cast --propose`; seither bleibt sie bei Wiederholung stehen, `--reset` verwirft sie) unter `casting/casting.yaml` (von Hand, gewinnt; u. a. die 6 früheren Sprecher, Jola, Meluna, Reija). Steckbriefe: `casting/profiles.jsonl`.
- Fehlende Typen: echte Kinderstimmen, alte Frauen (nur eine Stimme + Variante), helle Männerstimmen.
- Ältere Besetzung der 6 Sprecher (Adela `melanie`, Jero `german_wisdom_m_3130ae`, Enya `lena`, Femke `schales_7ef3ea` männlich, Gerion `lukas`, Gilwar `jonas`; `default_player: leon`) steht weiter in `casting.yaml` und gewinnt gegen die Auto-Zuteilung.

## Was im Spiel hörbar ist
`Mods/DrovaVoice/Audio/de/index.json` hat **13.819 Einträge**: alle 245 benannten Sprecher und die Aussagen des Spielers (ohne Auswahloptionen), 171 benannte und 152 generische Barks sowie 205 generische Dialogzeilen als Poolvarianten (`#vm1` … `#vw3`); OGG 48 kHz mono, −16 LUFS. Im Spiel abgenommen: Dialoge der benannten Sprecher (Stichprobe nach dem Vollauf), Barks inklusive Stimmwahl nach Geschlecht und Entfernungsregelung. **Noch nicht gehört:** die 205 generischen Dialogzeilen.

## Barks (Plan 7), Kurzfassung
- Index: 13.819 Einträge (2.142 Poolvarianten); 1.082 davon unter `bark/` (171 benannte Barks, 152 generische × 6 Poolstimmen). `casting/pools.yaml`: m `jonas, ben_a20517, schales_7ef3ea`, w `emma, catrinja_c5b66a, amira_german_b59d11`.
- Mod: `FigureReader` (Figur der Aussage), `PoolVoice` (Wahl), `BarkDistance` (Aussage freigeben und Entfernung). **Falle:** `statement.audio` einer geteilten Aussage bleibt stehen → ohne Freigabe spielt jede Figur die Stimme der ersten und der Connector läuft nicht mehr (Befund: `docs/playback.md`, Abschnitt Barks).
- Probe: `BarkProbe = true` loggt `[Figur]`-Zeilen; Befunde in `docs/decisions/2026-10-bark-figur-probe.md` und `…-bark-entfernung.md`. Ohne `--category` nimmt `synth` auch alle Poolzeilen mit.

## Entscheidungen, die man nicht wieder aufrollen soll
- **Engine:** Fish Audio Cloud; Kitten nur lokale Rückfallebene (`docs/decisions/2026-10-tts-engine.md`). Texte gehen an Fish: **nur nach ausdrücklichem Ja des Nutzers**. Kosten/Tarif für den Vollauf ungeklärt (~13.000 Zeilen).
- **Spielerauswahl bleibt stumm** wie im Original (Spiel hat `saySelection` aus): Der Generator überspringt Antwortoptionen (`player_choice`, 6.491 Zeilen); nur 119 Aussagen des Spielers werden gesprochen (`docs/decisions/2026-10-player-choices-stumm.md`).
- **Regler:** im Optionsmenü des Spiels (Plan 8); `MelonPreferences.cfg` liefert nur die Startwerte, das Menü gewinnt ab dem ersten Öffnen (`docs/playback.md`).
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
2. Danach Mod-Ausbau: Briefe (M7). Die Regler im Spiel sind erledigt (Plan 8). Barks (M6) sind erledigt (Plan 7); offen aus dem Review: Minors in `BarkDistance` (Zeitüberschreitung nach Zeit statt Frames, Scan teilen, Fehlerbehandlung) und die Same-Frame-Grenze (`docs/playback.md`, Abschnitt Barks).
3. Offene Lücken: 98-%-Lücke im Export (1.181 Zeilen ohne Sprecher; Lösungsansatz in `docs/decisions/2026-10-export-findings.md`), Jero und Adela im Spiel noch nie gehört, Regler-Wirkung (z. B. 150 %) im Spiel nicht geprüft. Namensvarianten: ca. 95 Namenszeilen werden neutral gesprochen (`…#neutral`); ca. 150 `gvar_name`- und ca. 150 `gvar_value`-Zeilen bleiben stumm.
4. Git: erledigt (2026-10-15). Historie umgeschrieben (Autor GitHub-noreply), Backup-Branches gelöscht; Pläne 1 bis 7 sind in `main` gemergt und gepusht (`main` = `origin/main`); MIT-Lizenz und README da.

## Wo steht was
- Specs und Pläne: `docs/superpowers/specs/`, `docs/superpowers/plans/` (Plan 4: `2026-10-14-plan-4-wiedergabe*.md`).
- Befunde: `docs/decisions/*.md`; Vertrag Generator ↔ Mod: `docs/audio-format.md`; Mod-Bedienung und Fehlersuche: `docs/playback.md`; Export: `docs/export.md`.
- Gedächtnis (außerhalb des Repos): `C:\Users\jpmin\.claude\projects\D--Games-Projekte-DrovaTTAI\memory\` (`plan-1/2/4-status.md`).
