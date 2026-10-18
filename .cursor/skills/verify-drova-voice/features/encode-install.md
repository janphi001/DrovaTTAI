# Encode and install

Encode turns the synthesized WAV into an OGG clip. Install copies that clip and an index into the game mod folder. In this cloud run the game folder is the temporary `game_dir`.

## Sub-features

- `encode-ogg` writes a mono 48 kHz Vorbis file for the Adela line.
- `install-temp` copies that file into the temporary game folder and writes `index.json`.
- `install-silent-choice` does not install the player choice.

## How to get to it (user POV)

- Run `drova-voice encode` after synth.
- Run `drova-voice install` to copy clips into `<game>/Mods/DrovaVoice/Audio/de/`.
- Filtered forms (`--npc`, `--sample`, `--batch`, `--category`) are further entry points. This cloud proof drives the unfiltered commands only. Do not mark the filtered forms as verified.

## Driving it with control-drova-voice

Preconditions:

- `synth --engine fake` has succeeded for this run.
- `control-drova-voice doctor` reports `ready: yes`.
- `game_dir` is the temporary run directory, not a Steam install.

- **Encode.** Run `control-drova-voice cli -- encode`. Exit code `0`. Stdout contains `1 kodiert` and `0 Fehler`. `network: clean`.
- **Install.** Run `control-drova-voice cli -- install`. Exit code `0`. Stdout contains `1 Dateien kopiert, index.json mit 1 Einträgen` and the install directory under `Mods/DrovaVoice/Audio/de`. `network: clean`.
- **Confirm the files.** Run `control-drova-voice snapshot --label after-install`. The install tree contains `dialog/7735cd9f80d47e45.ogg`. ffprobe on that file reports `codec_name=vorbis`, `channels=1`, `sample_rate=48000`, and a duration greater than 0. `index.json` has `version` `1`, `language` `de`, and one entry keyed by `DT_Verify_Probe|Dialog/NPC_Probe|Plh_1`. The choice id `DT_Verify_Probe|Dialog/NPC_Probe|Plh_2|c0` is absent. The encoded copy under `out/audio/de/dialog/` has the same sha256 as the installed file.

## Gotchas

- Installing into a real Drova folder is outside this cloud run. The temporary `game_dir` is the only install target the harness config allows.
- The C# mod that would play the index is nicht in der Cloud verifizierbar. A written `index.json` does not prove in-game playback.
- Encode fails closed when `results.jsonl` is missing. Do not point encode at a hand-made WAV.
- Player choice audio must not appear. An index that contains the choice id fails the proof even if encode printed success.
- `ffmpeg` must provide `libvorbis`. Doctor already checks that; a later `libvorbis fehlt` error means the binary on `PATH` changed.
