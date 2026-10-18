# Report status

Report prints how many lines are installed, encoded, synthesized, failed, open, or skipped. It is the user-facing check after install.

## Sub-features

- `report-category` summarizes status per category.
- `report-installed` shows the Adela line as installed.
- `report-choice` shows the player choice as skipped.

## How to get to it (user POV)

- Run `drova-voice report` after install.
- Run `drova-voice report --by-speaker` for a per-speaker view. This cloud proof drives the category view only. Do not mark `--by-speaker` as verified.

## Driving it with control-drova-voice

Preconditions:

- Install has succeeded for this run and `index.json` exists in the temporary audio folder.
- `control-drova-voice doctor` reports `ready: yes`.

- **Category report.** Run `control-drova-voice cli -- report`. Exit code `0`. Stdout contains `dialog: 1 Zeilen -> installiert: 1` and `player: 1 Zeilen -> übersprungen: player_choice: 1`.
- **Match the index.** Compare that stdout with `snapshot --label after-install` (or run `control-drova-voice snapshot --label after-report` if the install snapshot is missing). The single index entry is the dialog line, and the report's installed count is 1.

## Gotchas

- Report reads the install index inside `game_dir`. Pointing `game_dir` at another run makes the status look empty or stale.
- A skipped choice is a successful silence, not an open line. `übersprungen: player_choice: 1` must stay in the output.
- `--by-speaker` is a different view. Passing the category report does not verify it.
- The C# mod is nicht in der Cloud verifizierbar. Report does not start the game.
