---
name: verify-drova-voice
description: Drive the drova-voice Python CLI (extract, cast, synth, encode, install, report) with the local fake engine in workers/fake. Use when proving generator behavior or checking a pipeline change. No Fish calls and no game install. The C# mod is nicht in der Cloud verifizierbar.
---

# Verify drova-voice

Prove the generator CLI the way a user runs it. The surface is the `drova-voice` command in `generator/` (Python 3.11+, console script `drova-voice = drova_voice.cli:main`). The C# MelonLoader mod under `mod/` plays audio inside Drova on Windows. That mod is **nicht in der Cloud verifizierbar**: do not build it, do not set `DeployToGame`, and do not start the game.

Verification uses the fake engine (`generator/workers/fake/worker.py`, model `sine-1`). It writes a local sine WAV and does not read `FISH_API_KEY`. `synth` without `--engine` defaults to `fish` and is refused by the harness. Fish stays out of this skill.

There is no long-lived server. Launch installs the CLI once, seeds an isolated run, then each drive is its own tmux session. Two runs can proceed side by side: they share `generator/.venv` and nothing else. Set `DROVA_VOICE_VERIFY_RUN` to the run you launched. Do not drive a run this verification did not create.

The maintained map is `features/`. Read `features/README.md` before driving.

## Launch

From the repo root:

```bash
.cursor/skills/verify-drova-voice/scripts/control-drova-voice launch
source /tmp/drova-voice-verify/runs/$DROVA_VOICE_VERIFY_RUN/env.sh
```

`launch` prints `source: <run>/env.sh`. Source that file. It exports `DROVA_VOICE_VERIFY_RUN`, `DROVA_VOICE_VERIFY_MANIFEST`, and `DROVA_VOICE_VERIFY_EVIDENCE` (that run's evidence directory). A later `launch` in the same shell still writes the new run under `/tmp/drova-voice-verify/evidence/<new-run-id>/`. Override the evidence root only with `DROVA_VOICE_VERIFY_EVIDENCE_ROOT`.

What launch does:

1. Create `generator/.venv` with `python3 -m venv` and `pip install -e ".[dev]"` when `generator/.venv/bin/drova-voice` is missing. Later launches reuse that editable install. On Debian/Ubuntu, `python3 -m venv` needs the distro package `python3.12-venv` (this cloud image did not have it). Install that package when launch fails with `ensurepip is not available`, delete a half-created `generator/.venv`, and launch again. Do not commit the venv. `strace` must be on `PATH` before the first drive.
2. Create `/tmp/drova-voice-verify/runs/<run-id>/` with `config.yaml`, a copy of `casting/`, and an empty `root/` that becomes `repo_root` (`data/`, `cache/`, `out/` land there, not in the git checkout).
3. Point `game_dir` at `<run>/game`. The invented loc file is written to `<run>/game/Drova_Data/StreamingAssets/Localization/de/Dialog/NPC_Probe_de.loc`. The invented manifest is `<run>/fixture/manifest.json` (same bytes as `scripts/fixture/manifest.json`). Neither file is game dialogue.
4. Print `ready: yes` only after the doctor checks below pass.

Ready means the venv CLI answers `--help`, ffmpeg has `libvorbis`, ffprobe and `strace` are on `PATH`, the fake worker file exists, `FISH_API_KEY` is unset, and the config's `game_dir` and `repo_root` stay inside this run. A missing manifest is not ready.

Teardown is `cleanup` in the Cleanup section. Launch does not start the mod or the game.

## Doctor

Run this first whenever a drive looks wrong:

```bash
.cursor/skills/verify-drova-voice/scripts/control-drova-voice doctor
```

It is read-only. It prints `ready: yes` or `ready: no` plus `problem:` lines, and writes the same text to `$DROVA_VOICE_VERIFY_EVIDENCE/doctor.txt`. Drive only when `ready: yes`, `fish_api_key: absent`, `mod: nicht in der Cloud verifizierbar`, and `game_dir` is the run's `game/` directory.

`cli` runs the same checks before every command and refuses to start when they fail.

## Drive

The harness is `control-drova-voice`. It starts a tmux session (`/exec-daemon/tmux -f /exec-daemon/tmux.portal.conf` when that binary exists), unsets `FISH_API_KEY`, and runs:

```text
generator/.venv/bin/drova-voice --config <run>/config.yaml <args>
```

Stdout, stderr, the exit code, and the pane transcript are saved under the evidence directory. The command runs under `strace -f -e trace=execve,connect`, because `unshare --net` returns `Operation not permitted` here and a /proc poll can miss a short-lived worker. A clean drive is that trace: no `execve` of `workers/fish/worker.py`, a `synth` trace contains `execve` of `workers/fake/worker.py`, and no `connect` targets a non-loopback address. The flag `--engine fake` is not proof by itself. Polling `/proc/<pid>/fd` is not used: other processes in the pane tree are not readable, and the worker can exit between polls.

The harness returns the CLI exit code when that observation is clean. It returns `3` when the observation is dirty, and `2` when the command would call Fish (`synth` without `--engine fake`, the token `fish`, or `bakeoff`).

Stable handles are the subcommands and flags in `generator/drova_voice/pipeline.py`: `extract --manifest`, `cast --check`, `synth --engine fake`, `encode`, `install`, `report`. Quoted fixture strings stay literal:

- Speech (Adela, already mapped to `melanie` in `casting/casting.yaml`): `Die Probe klingt klar und fertig.`
- Player choice, which must stay silent: `Diese Auswahl bleibt stumm.`
- Line id: `DT_Verify_Probe|Dialog/NPC_Probe|Plh_1`
- Choice id: `DT_Verify_Probe|Dialog/NPC_Probe|Plh_2|c0`

Follow one feature file at a time. The cloud proof path is the unfiltered chain: default `extract` (expected failure, no game export), then `extract --manifest`, `cast --check`, `synth --engine fake`, `encode`, `install`, `report`. Take the extract snapshot before `export world`: that command writes `manifest-world.jsonl`, and a later extract mentions the file even when it is empty.

`export world` is its own feature. On a fresh run the bundle folder is missing, so the command exits `2` and stderr contains `Bundle-Ordner nicht gefunden`. `launch` installs `.[dev]` only. Proving that a broken bundle is skipped needs `pip install -e ".[assets]"` in `generator` once. Do not commit the venv. Do not copy game bundles into the run.

## Evidence

Evidence lives in `/tmp/drova-voice-verify/evidence/<run-id>/`. Cleanup never deletes that directory.

Each `cli` step writes `NNN-<command>/` with `command.txt`, `stdout.txt`, `stderr.txt`, `exitcode.txt`, `pane.txt`, `strace.txt`, `processes.txt` (execve lines), `sockets.txt` (external connect lines), and `network.txt`. `doctor.txt` and `run.json` sit beside those steps. `snapshot --label <name>` copies `lines.jsonl`, synth results, `encoded.jsonl`, `usage.jsonl`, `index.json`, and the small WAV/OGG files, plus `inventory.txt` (size, sha256, ffprobe).

Proof standard:

- Exercise `drova-voice` through the harness. Do not call `build_lines`, `run_synth`, or other internals, and do not use a test-only endpoint.
- Capture the command, stdout, stderr, and exit code, then a second view of the files those commands wrote.
- `extract` is proven by `data/lines.jsonl`: Adela's `speech` equals the loc sentence, and the choice row has `speech` `""` and `skip` `player_choice`.
- `synth --engine fake` is proven by a non-empty WAV under `<run>/root/cache/synth/`, a results row with `"ok": true` and `"engine"` not required in the row (the usage row's `engine` is `fake`), stderr from the worker containing `fake: synth`, `fake_worker_seen: yes`, and `network: clean`. No byte is sent to Fish.
- `encode` is proven by an OGG under `<run>/root/out/audio/de/dialog/7735cd9f80d47e45.ogg` (sha1 of the line id, first 16 hex digits). ffprobe reports `codec_name=vorbis`, `channels=1`, `sample_rate=48000`, and a duration greater than 0.
- `install` is proven by the same OGG under `<run>/game/Mods/DrovaVoice/Audio/de/dialog/` and by `index.json` whose only entry is the Adela line id. The choice id is absent.
- `report` is the user-facing second view: `dialog: 1 Zeilen -> installiert: 1` and `player: 1 Zeilen -> übersprungen: player_choice: 1`.
- The default `extract` (no `--manifest`) must fail with exit `2` and `Manifest nicht gefunden`. Record it as an unmet precondition, not as a passed extract.

## Cleanup

```bash
.cursor/skills/verify-drova-voice/scripts/control-drova-voice cleanup
```

Cleanup kills the tmux sessions recorded for this run (by session name, never by process name) and deletes `/tmp/drova-voice-verify/runs/<run-id>/`. It leaves `/tmp/drova-voice-verify/evidence/<run-id>/` in place. Confirm `evidence_exists: yes` after cleanup. It does not remove `generator/.venv`.

Run cleanup after a failed drive too, so a broken attempt does not leave a tmux session. Launch a new run afterwards; do not reuse a deleted run id.

## Helpers

| Helper | Invocation |
| --- | --- |
| Launch an isolated run | `.cursor/skills/verify-drova-voice/scripts/control-drova-voice launch` |
| Read-only readiness | `.cursor/skills/verify-drova-voice/scripts/control-drova-voice doctor` |
| One CLI command in its own tmux session | `.cursor/skills/verify-drova-voice/scripts/control-drova-voice cli -- extract --manifest "$DROVA_VOICE_VERIFY_MANIFEST"` |
| Copy side effects into evidence | `.cursor/skills/verify-drova-voice/scripts/control-drova-voice snapshot --label after-install` |
| Stop sessions and delete the run scratch | `.cursor/skills/verify-drova-voice/scripts/control-drova-voice cleanup` |

The script is executable. Its commands are `launch`, `doctor`, `cli`, `snapshot`, and `cleanup`. Fixture bytes live in `scripts/fixture/manifest.json` and `scripts/fixture/NPC_Probe_de.loc`.

When the CLI gains or changes a user-facing command, update `features/` with `/maintain-verification-skill`.
