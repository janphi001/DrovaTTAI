# Generator bedienen (Plan 3)

Der Generator `drova-voice` macht aus dem Export Sprachdateien für die Mod. Alle Befehle laufen im Ordner `generator/` (Git Bash: `.venv/Scripts/drova-voice ...`).

## Voraussetzungen

- Die Python-Umgebung `generator/.venv` (siehe `docs/setup.md`) und `generator/config.yaml` mit `game_dir` und `language` (Vorlage `config.example.yaml`).
- `ffmpeg` und `ffprobe` im PATH, ffmpeg mit `libvorbis`.
- Für Fish: Umgebungsvariable `FISH_API_KEY` in der Shell. Der Schlüssel steht nie in Dateien oder Befehlen.
- Der Export aus dem Spiel liegt unter `data/export/de/manifest.json` (siehe `docs/export.md`). Wer nur `manifest-loaded.json` hat, übergibt es mit `extract --manifest <Pfad>`.

## Reihenfolge

Jeder Schritt nimmt `--npc <Name>` und arbeitet dann auf allen Dialogbäumen, in denen dieser NPC spricht (Spieler-Auswahloptionen derselben Bäume werden als `player_choice` übersprungen, siehe unten). Ohne `--npc` gilt alles.

| Schritt | Befehl | Ergebnis |
|---|---|---|
| 1 | `drova-voice extract` | `data/lines.jsonl` (Sprechtext, Regieanweisungen, Gründe fürs Überspringen) |
| 2 | `drova-voice cast --check --npc Adela` | prüft, ob jeder Sprecher eine Stimme hat (`casting/casting.yaml`) |
| 3 | `drova-voice emote --npc Adela` | `casting/emotions.jsonl` (aus Regieanweisungen; `llm`- und `manual`-Zeilen bleiben) |
| 4 | `drova-voice synth --npc Adela` | WAVs in `cache/synth/`, Protokoll `data/synth/results.jsonl` |
| 5 | `drova-voice encode --npc Adela` | OGG in `out/audio/<Sprache>/`, Protokoll `data/encoded.jsonl` |
| 6 | `drova-voice install --npc Adela` | Dateien und `index.json` in `<Spiel>/Mods/DrovaVoice/Audio/<Sprache>/` |
| 7 | `drova-voice report --npc Adela` | Status je Kategorie |
| 8 | `drova-voice preview --npc Adela` | Hörseite `out/preview/index.html` |

`synth` hat `--engine` (Standard `fish`; `fake` für Tests ohne Netz), `--workers` (Standard 8) und `--limit N` (nur die ersten N Aufträge, zum Ausprobieren).

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

`--sample` und `--batch N` gelten für `synth`, `encode`, `install`, `report` und `preview`. Varianten (`voice: alte_frau` in `casting.yaml`) werden mit der Basisstimme erzeugt und beim Kodieren per ffmpeg (`rubberband`) umgeformt. Der Zeichenverbrauch je Lauf steht am Ende der `synth`-Ausgabe und in `data/synth/usage.jsonl`.

`profile --import` und `emote --import` brechen bei einer fehlenden Importdatei ab (Exit 2) und melden unlesbare Zeilen (Exit 1), schreiben aber die gültigen Zeilen.

## Wo was liegt

- `casting/` gehört ins Git (nur Stimmenschlüssel, Labels, Emotionen): `fish_voices.yaml`, `casting.yaml`, `emotions.jsonl`, `lexicon.yaml`.
- Alles andere ist abgeleitet und darf gelöscht werden: `data/`, `cache/`, `out/`. Der Mod-Ordner wird beim nächsten `install` neu befüllt.
- Das Format der Dateien im Mod-Ordner steht in `docs/audio-format.md`.

## Wiederaufnehmen und Neu-Erzeugen

- Jeder Schritt ist wiederaufnehmbar. `synth` legt fertige WAVs unter `cache/synth/<Schlüssel>.wav` ab; der Schlüssel enthält Engine, Modell, Stimme, gerenderten Text (inklusive Emotions-Cues) und Parameter. Ändern sich Text, Stimme oder Emotion, wird automatisch neu erzeugt.
- Erzwingen: die WAV in `cache/synth/` löschen und `synth` wiederholen. Danach `encode` und `install`.
- Abbruch mittendrin (Strg+C, Netz weg) verliert höchstens die laufenden Anfragen. Halbe Dateien tragen `.part` im Namen und werden nie verwendet.
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
- Stand 2026-10-15: 171 benannte und 152 generische Barks (6 Poolstimmen) vertont und installiert; die 205 generischen Dialogzeilen (`dialog`, Pool) stehen noch aus.
- Besetzung: `casting/casting.yaml` (von Hand, gewinnt) über `casting/casting_auto.yaml` (erzeugt).
- Fish ist eine Cloud-Engine: der Sprechtext geht an `api.fish.audio`. Nur nach ausdrücklichem Ja des Nutzers mit echten Spieltexten benutzen.
