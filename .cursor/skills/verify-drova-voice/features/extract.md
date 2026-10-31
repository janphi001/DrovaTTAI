# Extract lines

Extract turns a dialogue manifest and localization files into `data/lines.jsonl`, including which lines are speakable and which stay silent.

## Sub-features

- `extract-default` looks for `data/export/de/manifest.json`, then `manifest-loaded.json` in that same directory.
- `extract-manifest` reads an explicit manifest and the run's `.loc` files.
- `extract-speech` keeps the localization sentence as the speakable text.
- `extract-player-choice` records the player choice as skipped and unspoken.

## How to get to it (user POV)

- Run `drova-voice extract` after a game export has been fetched.
- Run `drova-voice extract` when `manifest.json` is absent and `manifest-loaded.json` is in the same export directory.
- Run `drova-voice extract --manifest <path>` when the manifest is not the default export file.

## Driving it with control-drova-voice

Preconditions:

- `control-drova-voice doctor` reports `ready: yes` for this run.
- `$DROVA_VOICE_VERIFY_MANIFEST` points at the run fixture.
- The loc fixture contains `Die Probe klingt klar und fertig.` and `Diese Auswahl bleibt stumm.`
- No `data/lines.jsonl` exists yet in this run.

- **Default export path.** Run extract with no manifest. Run `control-drova-voice cli -- extract`. Exit code `2`. Stderr contains `Manifest nicht gefunden` and `manifest-loaded.json`. This entry stays unverified. The fresh cloud run has neither export file. Do not treat the failure as a successful extract.
- **Loaded manifest.** Place the run fixture at `data/export/de/manifest-loaded.json` and leave `manifest.json` absent. Run `control-drova-voice cli -- extract`. Exit code `0`. Stdout contains `manifest-loaded.json`, `manifest.json fehlt`, `2 Zeilen`, and `übersprungen: player_choice: 1`. `lines.jsonl` has the same two rows as the explicit-manifest snapshot. Extract overwrites `lines.jsonl`. Run the loaded-manifest command after the explicit-manifest snapshot, or on a fresh run before that snapshot.
- **Explicit manifest.** Run `control-drova-voice cli -- extract --manifest "$DROVA_VOICE_VERIFY_MANIFEST"`. Exit code `0`. Stdout contains `2 Zeilen` and `übersprungen: player_choice: 1`.
- **Confirm the lines file.** Run `control-drova-voice snapshot --label after-extract`. `lines.jsonl` has two rows. The Adela row `DT_Verify_Probe|Dialog/NPC_Probe|Plh_1` has `speech` equal to `Die Probe klingt klar und fertig.` The choice row `DT_Verify_Probe|Dialog/NPC_Probe|Plh_2|c0` has `speech` equal to `""` and `skip` equal to `player_choice`.

## Gotchas

- The default path fails only when `manifest.json` and `manifest-loaded.json` are both missing. A present `manifest-loaded.json` is a successful extract. Do not record that success as the missing-export failure.
- Localization text wins over the manifest text. Assert `speech` from `lines.jsonl`, not the manifest alone.
- A player choice remains in the file with an empty `speech`. Deleting the row would hide a line that must stay silent.
- Speaker name `Adela` is required because the copied casting map gives her a voice. An unknown speaker makes the later cast check fail; do not rename the fixture to force a pass.
- The fixture sentences are invented. Do not replace them with lines from the game.
- `manifest-runtime.jsonl` and `manifest-world.jsonl` are optional files beside the export. A missing file adds no rows and no status line. The fresh cloud run has neither file, so the explicit-manifest stdout is only the `2 Zeilen` line.
- After `export world` writes `manifest-world.jsonl`, the next extract mentions it even when the file is empty: `0 Welt-Dialog-Zeilen aus manifest-world.jsonl (0 schon bekannt, 0 unlesbar)`. This fixture still prints `2 Zeilen` and `übersprungen: player_choice: 1`. Take the two-line snapshot before export world.
