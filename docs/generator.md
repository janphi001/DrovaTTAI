# Generator bedienen (Plan 3)

Der Generator `drova-voice` macht aus dem Export Sprachdateien für die Mod. Alle Befehle laufen im Ordner `generator/` (Git Bash: `.venv/Scripts/drova-voice ...`).

## Voraussetzungen

- Die Python-Umgebung `generator/.venv` (siehe README, Abschnitt „Generator einrichten“) und `generator/config.yaml` mit `game_dir` und `language` (Vorlage `config.example.yaml`).
- `ffmpeg` und `ffprobe` im PATH, ffmpeg mit `libvorbis`.
- Für Fish: Umgebungsvariable `FISH_API_KEY` in der Shell. Der Schlüssel steht nie in Dateien oder Befehlen.
- Der Export aus dem Spiel liegt unter `data/export/<Sprache>/` (siehe `docs/export.md`). `extract` und `export report` nehmen `manifest.json`. Fehlt die Datei, nehmen sie `manifest-loaded.json` (das schreibt `export.trigger`). Ein anderer Pfad geht mit `--manifest`.

## Reihenfolge

Jeder Schritt nimmt `--npc <Name>` und arbeitet dann auf allen Dialogbäumen, in denen dieser NPC spricht (Spieler-Auswahloptionen derselben Bäume werden als `player_choice` übersprungen, siehe unten). Ohne `--npc` gilt alles.

| Schritt | Befehl | Ergebnis |
|---|---|---|
| 0 | `drova-voice export fetch` | kopiert den Export-Ordner aus dem Spiel nach `data/export/<Sprache>/`, auch `manifest-runtime.jsonl` (siehe unten) |
| 0b | `drova-voice export world` | liest die Welt-Dialoge des Vorlagen-Baums aus den Bundles des Spiels nach `data/export/<Sprache>/manifest-world.jsonl` (siehe unten; braucht `uv sync --extra assets`) |
| 1 | `drova-voice extract` | `data/lines.jsonl` (Sprechtext, Regieanweisungen, Gründe fürs Überspringen) |
| 2 | `drova-voice cast --check --npc Adela` | prüft, ob jeder Sprecher eine Stimme hat (`casting/casting.yaml`) |
| 3 | `drova-voice emote --npc Adela` | `casting/emotions.jsonl` (aus Regieanweisungen; `llm`- und `manual`-Zeilen bleiben) |
| 4 | `drova-voice synth --npc Adela` | WAVs in `cache/synth/`, Protokoll `data/synth/results.jsonl` |
| 5 | `drova-voice encode --npc Adela` | OGG in `out/audio/<Sprache>/`, Protokoll `data/encoded.jsonl` |
| 6 | `drova-voice install --npc Adela` | Dateien und `index.json` in `<Spiel>/Mods/DrovaVoice/Audio/<Sprache>/` |
| 7 | `drova-voice report --npc Adela` | Status je Kategorie |
| 8 | `drova-voice preview --npc Adela` | Hörseite `out/preview/index.html` |

`synth` hat `--engine` (Standard `fish`; `fake` für Tests ohne Netz), `--workers` (Standard 8), `--limit N` (nur die ersten N Aufträge, zum Ausprobieren; `0` sendet nichts) und `--max-utf8-bytes N` (Budget für neu gesendete UTF-8-Bytes).

`install --prune` löscht im Zielordner OGG-Dateien, die danach kein Indexeintrag mehr nennt. Ohne die Option bleiben sie liegen. `install --dry-run` kopiert nichts und schreibt `index.json` nicht; es zählt und listet nur (`würde N kopieren, M Einträge, K verwaist`). Zusammen mit `--prune` gilt der Dry-Run. Beides ist standardmäßig aus.

## Welt-Dialoge (`export world`, `manifest-world.jsonl`)

Viele Welt-Dialoge haben keinen eigenen Baum: Das Spiel baut sie zur Laufzeit aus `DT_WorldDialogue_Template`. Die Daten stehen in `WorldDialogueStarterModule._worldDialogueSettings` (`_graphLocaPath`, `Args` mit `_path`, `_key`, `Participant`) auf Komponenten in Prefabs und Szenen (`Interact_Bhvr_*`, `PPT_Bhvr_WorldDialog`, `HitReceiveBhvr_WorldDialogue`, `WorldDialogueContainer` …). `export world` liest sie offline aus allen Addressables-Bundles (`Drova_Data/StreamingAssets/aa/StandaloneWindows64`, TypeTrees über UnityPy, 8 Prozesse, `--workers`) und schreibt je Pfad und Schlüssel eine Manifestzeile mit der ID `DT_WorldDialogue_Template|<Pfad>|<Schlüssel>`. Module mit eigenem Baum (`_useTree`) stehen schon im normalen Export und zählen nicht.

- Sprecher: `Participant` des Args, sonst die `EntityInfo` des Besitzers (Komponente mit `_entityInfo` auf dem GameObject oder darüber), über `npcs.json` auf den Sprechernamen des Spiels abgebildet. Ohne beides ist es ein Objekt (Statue, Erzader, Kiste …): Dort spricht der Spieler; unter `CrimesReactions` eine generische Figur (`NPC`). Teilen sich mehrere Module einen Schlüssel mit verschiedenen Sprechern, gewinnt der häufigste.
- Kategorie wie in der Mod: Spieler `player`, sonst `bark` (Baum beginnt mit `DT_World`).
- Der Text kommt beim `extract` aus den `.loc`-Dateien.
- Stand 2026-10-20: 2.183 Bundles, 4.671 Module, davon 2.260 mit Vorlage, 836 Zeilen. Geprüft gegen das Spiel-Log: `Dialogues/WorldDialogue|Plh_10` spricht Almar (Participant), `Plh_11` Merik (Participant statt Besitzer Almar).

## Laufzeit-Zeilen (`manifest-runtime.jsonl`)

Manche Aussagen sieht der Export nicht, vor allem Vorlagen-Bäume wie `DT_WorldDialogue_Template`, deren Loca-Pfad erst im Spiel feststeht (dieselben Schlüssel unter `Dialogues/WorldDialogue`, `WoodcampWorldDialogue` …). Die Mod hängt jede ausgeführte Aussage ohne Indexeintrag (und ohne Poolvarianten) einmal an `<Spiel>/Mods/DrovaVoice/Export/<Sprache>/manifest-runtime.jsonl` an: eine Manifestzeile je Textzeile, mit dem Sprecher der Aussage (`actorName`). Die Datei wächst mit jeder Spielsitzung und enthält Spieltext (nie ins Git).

`export fetch` kopiert sie mit, `extract` nimmt sie zum Manifest dazu (Reihenfolge bei gleicher ID: Manifest, Laufzeit-Zeilen, Welt-Dialoge) und meldet `N Laufzeit-Zeilen …`. Danach behandeln alle Schritte sie wie Exportzeilen, ein Vollauf (`batches`, `synth --batch` …) also auch. Neue Sprecher meldet `cast --check`; Gründe fürs Überspringen (`gvar_value` …) gelten wie sonst.

## Casting und Vollauf (Plan 5)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| a | `profile --prepare` | Pakete mit Sprecherauszügen unter `out/subagent/profile/` (enthalten Spieltexte, nie ins Git) |
| b | `profile --import <Dateien>` | prüft die JSONL-Ergebnisse der Subagents und schreibt `casting/profiles.jsonl` (`manual`-Zeilen bleiben) |
| c | `profile --set NAME --gender m --age mittel [--type riese] [--note ...]` / `profile` | Steckbrief von Hand setzen / Prüfliste (unsichere Einträge markiert) |
| d | `cast --propose [--reset]` | `casting/casting_auto.yaml`; `casting.yaml` gewinnt; erste Zuteilung, danach bleibt die Auto-Zuteilung stehen (nur neue Sprecher werden zugeteilt); `--reset` verwirft sie und teilt alles neu zu (`--keep` ist nur noch Synonym des Standards) |
| e | `synth --sample`, `encode --sample`, `cast --listen` | Hörseite `out/casting/index.html`, eine Beispielzeile je Sprecher |
| f | `emote --prepare`, `emote --import <Dateien>` | LLM-Emotionen für alle Dialogbäume (`stage`- und `manual`-Zeilen bleiben) |
| g | `batches [--max-chars N]` | Etappen nach Wichtigkeit in `data/batches.json` |
| h | `synth --batch N`, `encode --batch N`, `install --batch N` | eine Etappe erzeugen; `synth` bricht bei Guthaben-/Limit-/Anmeldefehlern nach 5 Fehlern in Folge sauber ab |
| i | `report --by-speaker` | Status und Lücken je Sprecher |

`--sample` und `--batch N` gelten für `synth`, `encode`, `install`, `report` und `preview`. Varianten (`voice: alte_frau` in `casting.yaml`) werden mit der Basisstimme erzeugt und beim Kodieren per ffmpeg (`rubberband`) umgeformt. Verbrauch je Lauf (Zeichen und UTF-8-Bytes je tatsächlich gesendeter Anfrage, inklusive Wiederholungen und fehlgeschlagener Anfragen) steht am Ende der `synth`-Ausgabe und in `data/synth/usage.jsonl` (`chars`, `utf8_bytes`, `requests`).

`profile --import` und `emote --import` brechen bei einer fehlenden Importdatei ab (Exit 2) und melden unlesbare Zeilen (Exit 1), schreiben aber die gültigen Zeilen.

## Wo was liegt

- `casting/` gehört ins Git (nur Stimmenschlüssel, Labels, Emotionen): `fish_voices.yaml`, `casting.yaml`, `emotions.jsonl`, `lexicon.yaml`.
- Alles andere ist abgeleitet und darf gelöscht werden: `data/`, `cache/`, `out/`. Der Mod-Ordner wird beim nächsten `install` neu befüllt.
- Das Format der Dateien im Mod-Ordner steht in `docs/audio-format.md`.

## Wiederaufnehmen und Neu-Erzeugen

- Jeder Schritt ist wiederaufnehmbar. `synth` legt fertige WAVs unter `cache/synth/<Schlüssel>.wav` ab; der Schlüssel enthält Engine, Modell, Stimme, gerenderten Text (inklusive Emotions-Cues) und Parameter. Ändern sich Text, Stimme oder Emotion, wird automatisch neu erzeugt.
- Das Fish-Modell steht im Schlüssel als Alias `fish-audio/<id>`. Sprache (`language` aus `config.yaml`), Latenz und Sampling (`temperature`, `top_p`) stehen nur darin, wenn sie vom Standard (`de`, `normal`, `0.7`, `0.7`) abweichen, denn mit genau diesen Werten entstand der vorhandene Cache. Die ID kommt aus `fish_model`, sonst aus `FISH_MODEL`, sonst `s2.1-pro-free`. Latenz und Sampling: `fish_latency`, `fish_temperature`, `fish_top_p`, sonst `normal`, `0.7`, `0.7`. `FISH_LATENCY`, `FISH_TEMPERATURE` und `FISH_TOP_P` überschreiben das für einen Lauf. `s2.1-pro-free` ist laut Fish-Changelog kostenlos bis 30.11.2026; der Nachfolger `s2.1-pro` kostet 15 USD je Million UTF-8-Bytes. Ein anderer Stempel ist ein Fehltreffer für alle vorhandenen WAVs. `synth` bricht ab und nennt den Wechsel. Erst `synth --accept-model-change` schreibt `cache/synth/fish-model.txt` und erzeugt neu. Cache ohne Stempel gilt als `fish-audio/s2.1-pro-free` (der bisherige Vollauf). Das Standardprofil hat genau diesen Stempel, ein Lauf mit Standardwerten trifft den alten Cache also ohne Rückfrage.
- Der Fish-Worker wiederholt eine Anfrage höchstens 3 Mal (Standard 2) und längstens `FISH_DEADLINE_S` Sekunden (Standard 240). Jeder POST zählt in `SynthResult.attempts` und in `data/synth/usage.jsonl` als `requests`. Ist der Worker mit den Transportversuchen durch (`nicht erreichbar`), startet `synth` dieselbe Zeile nicht noch einmal.
- `cast --check-voices` prüft die Fish-IDs der Besetzung (einschließlich Varianten-Basis und Pool) per `GET /model/{id}`. Ohne `FISH_API_KEY` endet der Befehl mit „übersprungen“ und Exit 0, ohne Netz. Fehlt eine Stimme und `casting/fish_voices.yaml` hat einen `fallbacks`-Eintrag, meldet die Prüfung `ERSATZ`. `synth` übernimmt den Ersatz nicht, weil das den Cache-Schlüssel ändert.
- Erzwingen: die WAV in `cache/synth/` löschen und `synth` wiederholen. Danach `encode` und `install`.
- Abbruch mittendrin (Strg+C, Netz weg) verliert höchstens die laufende Anfrage. Eine halbe `.part`-Datei wird verworfen. Eine schon vollständige WAV unter diesem Namen wird übernommen und nicht erneut angefordert.
- `synth --max-utf8-bytes N` bricht ab, bevor die nächste Anfrage das Budget an UTF-8-Bytes überschreitet. Cache-Treffer zählen nicht. Parallele Worker teilen sich dasselbe Budget.
- Gleicher Text mit gleicher Stimme wird nur einmal erzeugt.

## Grenzen von Plan 3

- Zeilen mit `$GVAR:` im Text: Ist der Spielername der einzige Platzhalter und lässt er sich streichen (`player_name.py`), wird die Zeile in neutraler Fassung vertont (ID `…#neutral`). Sonst übersprungen und im Bericht gezählt: `gvar_name` (Name steht mitten im Satz), `gvar_value` (Quest- oder Geldwerte, auch zusammen mit dem Namen).
- Spielerzeilen nutzen eine feste Stimme (`default_player`), keine Stimmsets. Gesprochen werden nur Aussagen des Spielers (119 im Spiel); **Auswahloptionen** (6.491 Zeilen) bleiben stumm wie im Original (Nutzerentscheidung 2026-10-15, Grund `player_choice`).
- Keine Briefe.

## Barks und Stimmenpool (Plan 7)
- `casting/pools.yaml`: je Geschlecht (`m`, `w`) eine Liste von Stimmenschlüsseln aus `fish_voices.yaml`; die Position ergibt den Tag (`vm1`, `vw2` …). Fehlt die Datei, bleiben generische Sprecher unbesetzt (wie vorher).
- Jede sprechbare Zeile eines generischen Sprechers wird beim Einlesen (`_selected`) durch eine Zeile je Poolstimme ersetzt (`<ID>#v<g><n>`, Feld `Line.pool`); `Casting.voice_for` ordnet die Stimme zu, Emotionen gelten über die Basis-ID (`emotion_id`). `emote` arbeitet auf den Basiszeilen.
- `--category dialog|bark|player` filtert `synth`, `encode`, `install`, `report`, `emote`, `preview`. **Ein `synth` ohne `--category` nimmt alle Poolzeilen (generische Dialogzeilen und Barks) mit** und sendet sie an Fish.
- Barks benannter Sprecher laufen wie normale Zeilen über die Besetzung; Ordner `bark/` ergibt sich aus der Kategorie. `install` baut die Poolvarianten einer Basis-ID jedes Mal neu auf (Pool verkleinert → alte Varianten verschwinden).
- Stand 2026-10-15: 171 benannte und 152 generische Barks (6 Poolstimmen) vertont und installiert; dazu 205 generische Dialogzeilen (`dialog`, Pool, 1.230 Clips). Index danach: 13.819 Einträge.
- Besetzung: `casting/casting.yaml` (von Hand, gewinnt) über `casting/casting_auto.yaml` (erzeugt).
- Fish ist eine Cloud-Engine: der Sprechtext geht an `api.fish.audio`. Nur nach ausdrücklichem Ja des Nutzers mit echten Spieltexten benutzen.

## Release-Paket

`drova-voice package` baut aus dem Spielordner ein ZIP für Spieler: `Mods/DrovaVoice.dll`, `UserLibs/DrovaVoice.Core.dll`, `UserLibs/NVorbis.dll`, `Mods/DrovaVoice/Audio/<Sprache>/` (nur die OGG-Dateien, auf die `index.json` zeigt) sowie `README.txt` und `LIZENZEN.txt` aus `release/`. Ziel ist `dist/DrovaVoice-<Version>-<Sprache>.zip` mit einer `.sha256` daneben; `dist/` steht nicht im Git. Die Version kommt aus `MelonInfo` in `mod/DrovaVoice/DrovaVoiceMod.cs`, `--version` überschreibt sie, `--out` wählt einen anderen Ordner.

Vorher die Mod bauen und ins Spiel kopieren (`-p:DeployToGame=true`) und im Spiel prüfen: Das Paket enthält genau, was dort liegt. Fehlt eine Datei aus dem Index, bricht der Befehl ab und schreibt kein ZIP. Der Text für die Ankündigung liegt in `release/discord-post.md`.
