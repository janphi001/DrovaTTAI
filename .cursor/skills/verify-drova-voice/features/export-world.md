# Export world dialogues

`drova-voice export world` reads asset bundles under the run's game directory and writes `data/export/<language>/manifest-world.jsonl`. A bundle that cannot be loaded is skipped. Extract appends rows from that file only when it already exists.

## Sub-features

- `export-world-missing-dir` fails when the bundle folder is absent.
- `export-world-no-assets` fails when the folder exists and UnityPy is not installed.
- `export-world-skip-broken` continues when a `*.bundle` file cannot be loaded and writes an empty world file when nothing was readable.
- `export-world-npc-list` warns when `npcs.json` is missing or is not a list, and does not abort.

## How to get to it (user POV)

- Run `drova-voice export world` when the game bundles are on disk.
- `--workers` sets scan parallelism. This cloud proof does not pass it.

## Driving it with control-drova-voice

Preconditions:

- `control-drova-voice doctor` reports `ready: yes` and `fish_api_key: absent`.
- Drive this after the two-line extract proof, or on a separate run. Do not re-run extract if the extract stdout must stay a single line.
- `launch` installs `.[dev]` only. The skip bullet needs `pip install -e ".[assets]"` in `generator` once. Do not commit the venv.

- **Missing bundle folder.** On a fresh run, run `control-drova-voice cli -- export world`. Exit code `2`. Stderr contains `Bundle-Ordner nicht gefunden` and a path under this run's `game/`. `network: clean`. This is not a successful export.
- **Folder without UnityPy.** Create `game/Drova_Data/StreamingAssets/aa/StandaloneWindows64` and run the same command before the assets extra is installed. Exit code `2`. Stderr contains `UnityPy fehlt`. When `data/export/<language>/npcs.json` is absent, stdout contains `npcs.json fehlt`.
- **Unreadable bundle.** After the assets extra is installed, put a non-bundle file named `broken.bundle` in that directory and a JSON object (not a list) at `data/export/<language>/npcs.json`. Run `control-drova-voice cli -- export world`. Exit code `0`. Stdout contains `1 Bundles, 0 Welt-Dialog-Module (0 mit Vorlage): 0 Zeilen` and `manifest-world.jsonl`. Stderr contains `keine Liste`. The world file is empty. `network: clean`. No Fish worker is executed.

## Gotchas

- The missing folder is checked first. A fresh run never reaches the UnityPy error or the `npcs.json` hint.
- A missing `npcs.json` hint goes to stdout. A non-list `npcs.json` hint goes to stderr. Neither hint is a failed export by itself.
- Zero modules and an empty world file prove that an unreadable bundle did not abort the command. They do not prove that game content was read. Do not copy game bundles into the run.
- An omitted file id on a Unity pointer counts as local. That case needs a bundle object graph, so this cloud run does not drive it. The unreadable-file bullet is the cloud proof that one bad bundle does not abort the export.
- `launch` does not install UnityPy into an existing `generator/.venv`. Install the assets extra only for the skip bullet.
- An empty `manifest-world.jsonl` still changes the next extract: it prints `0 Welt-Dialog-Zeilen aus manifest-world.jsonl (0 schon bekannt, 0 unlesbar)`.
- The C# mod is nicht in der Cloud verifizierbar. This command does not start the game.
