# Generator bedienen (Plan 3)

Der Generator `drova-voice` macht aus dem Export Sprachdateien für die Mod. Alle Befehle laufen im Ordner `generator/` (Git Bash: `.venv/Scripts/drova-voice ...`).

## Voraussetzungen

- Die Python-Umgebung `generator/.venv` (siehe `docs/setup.md`) und `generator/config.yaml` mit `game_dir` und `language` (Vorlage `config.example.yaml`).
- `ffmpeg` und `ffprobe` im PATH, ffmpeg mit `libvorbis`.
- Für Fish: Umgebungsvariable `FISH_API_KEY` in der Shell. Der Schlüssel steht nie in Dateien oder Befehlen.
- Der Export aus dem Spiel liegt unter `data/export/de/manifest.json` (siehe `docs/export.md`). Wer nur `manifest-loaded.json` hat, übergibt es mit `extract --manifest <Pfad>`.

## Reihenfolge

Jeder Schritt nimmt `--npc <Name>` und arbeitet dann auf allen Dialogbäumen, in denen dieser NPC spricht (inklusive der Spieler-Auswahloptionen in diesen Bäumen). Ohne `--npc` gilt alles.

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

- Zeilen mit `$GVAR:` im Text (Spielername, Quest-Werte) werden übersprungen und im Bericht als `gvar` gezählt. Namensvarianten folgen später.
- Spielerzeilen nutzen eine feste Stimme (`default_player`), keine Stimmsets.
- Keine Varianten für generische Sprecher, keine Barks, keine Briefe.
- Die Stimmenzuordnung in `casting/casting.yaml` ist vorläufig und wird nach dem Hörtest festgelegt.
- Fish ist eine Cloud-Engine: der Sprechtext geht an `api.fish.audio`. Nur nach ausdrücklichem Ja des Nutzers mit echten Spieltexten benutzen.
