# Extract lines

Extract turns a dialogue manifest and localization files into `data/lines.jsonl`, including which lines are speakable and which stay silent.

## Sub-features

- `extract-default` looks for the game export at `data/export/de/manifest.json`.
- `extract-manifest` reads an explicit manifest and the run's `.loc` files.
- `extract-speech` keeps the localization sentence as the speakable text.
- `extract-player-choice` records the player choice as skipped and unspoken.

## How to get to it (user POV)

- Run `drova-voice extract` after a game export has been fetched.
- Run `drova-voice extract --manifest <path>` when the manifest is not the default export file.

## Driving it with control-drova-voice

Preconditions:

- `control-drova-voice doctor` reports `ready: yes` for this run.
- `$DROVA_VOICE_VERIFY_MANIFEST` points at the run fixture.
- The loc fixture contains `Die Probe klingt klar und fertig.` and `Diese Auswahl bleibt stumm.`
- No `data/lines.jsonl` exists yet in this run.

- **Default export path.** Run extract with no manifest. Run `control-drova-voice cli -- extract`. Exit code `2`, and stderr contains `Manifest nicht gefunden`. This entry stays unverified: the cloud run has no game export. Do not treat the failure as a successful extract.
- **Explicit manifest.** Run `control-drova-voice cli -- extract --manifest "$DROVA_VOICE_VERIFY_MANIFEST"`. Exit code `0`. Stdout contains `2 Zeilen` and `übersprungen: player_choice: 1`.
- **Confirm the lines file.** Run `control-drova-voice snapshot --label after-extract`. `lines.jsonl` has two rows. The Adela row `DT_Verify_Probe|Dialog/NPC_Probe|Plh_1` has `speech` equal to `Die Probe klingt klar und fertig.` The choice row `DT_Verify_Probe|Dialog/NPC_Probe|Plh_2|c0` has `speech` equal to `""` and `skip` equal to `player_choice`.

## Gotchas

- The default manifest path needs a game export. Missing that file is a precondition failure, not a reason to skip the assertion.
- Localization text wins over the manifest text. Assert `speech` from `lines.jsonl`, not the manifest alone.
- A player choice remains in the file with an empty `speech`. Deleting the row would hide a line that must stay silent.
- Speaker name `Adela` is required because the copied casting map gives her a voice. An unknown speaker makes the later cast check fail; do not rename the fixture to force a pass.
- The fixture sentences are invented. Do not replace them with lines from the game.
- `manifest-runtime.jsonl` and `manifest-world.jsonl` are optional files beside the export. A missing file adds no rows and no status line. The fresh cloud run has neither file, so the explicit-manifest stdout is only the `2 Zeilen` line.
- After `export world` writes `manifest-world.jsonl`, the next extract mentions it even when the file is empty: `0 Welt-Dialog-Zeilen aus manifest-world.jsonl (0 schon bekannt, 0 unlesbar)`. This fixture still prints `2 Zeilen` and `übersprungen: player_choice: 1`. Take the two-line snapshot before export world.
