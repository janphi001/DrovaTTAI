# drova-voice verification map

This directory is the maintained source for verifying the user-facing behavior of the `drova-voice` CLI. Read the index before driving the app, then use the matching feature file as the recipe.

The C# mod under `mod/` is **nicht in der Cloud verifizierbar**. It needs Windows, Drova, and MelonLoader. Do not build it and do not deploy it into a game folder.

## Baseline preconditions

- Launch a disposable run with `.cursor/skills/verify-drova-voice/scripts/control-drova-voice launch` and source the printed `env.sh`.
- `DROVA_VOICE_VERIFY_RUN` selects the run. Concurrent runs must not share that variable.
- The run copies `casting/` and writes an invented manifest plus `NPC_Probe_de.loc`. The spoken sentence is `Die Probe klingt klar und fertig.` The player choice `Diese Auswahl bleibt stumm.` must stay silent.
- `control-drova-voice doctor` reports `ready: yes`, `fish_api_key: absent`, and a `game_dir` inside `/tmp/drova-voice-verify/runs/<run-id>/game`.
- Never drive an instance that was not started by this verification run.
- `FISH_API_KEY` stays unset. Synthesis uses `--engine fake` only.

## Driving conventions

- Start every recipe from the baseline state unless its preconditions say otherwise.
- Treat every command as literal. Keep quoted sentences and flags unchanged.
- Run every CLI action through `control-drova-voice cli -- <drova-voice args>`.
- Restore nothing in the git checkout. Scratch lives under the run directory.
- Do not remove proof artifacts during cleanup.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final stdout line.
- CLI proof includes the command, stdout, stderr, and exit code under `/tmp/drova-voice-verify/evidence/<run-id>/`.
- Mutation proof includes a read-only second view: `snapshot` plus, for install, `report`.
- A clean `synth` records `fake_worker_seen: yes`, `fish_worker_seen: no`, and `network: clean` from `strace -f -e trace=execve,connect`. The engine flag alone is not proof.
- Record the feature id and entry point used with every artifact.
- Report an unreachable path with the attempted command and the unmet precondition.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with control-drova-voice` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Extract lines](./extract.md) covers the invented manifest, the missing game export, and silent player choices.
- [Synthesize with the fake engine](./synth.md) covers cast check, fake synthesis, and the absence of Fish.
- [Encode and install](./encode-install.md) covers OGG encode and install into the temporary game folder.
- [Report status](./report.md) covers the status view after install.
- [Export world dialogues](./export-world.md) covers the missing bundle folder, a missing UnityPy install, and a bundle the scan skips.
