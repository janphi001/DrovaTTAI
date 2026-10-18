# Synthesize with the fake engine

Synth turns speakable lines into WAV files. Verification uses the fake engine, which writes a local tone and does not contact Fish.

## Sub-features

- `synth-cast` checks that every speakable line has a voice.
- `synth-fake` writes one WAV for the Adela line through `workers/fake`.
- `synth-no-fish` leaves Fish unused: no Fish worker and no external TCP socket.
- `synth-skip-choice` does not synthesize the player choice.

## How to get to it (user POV)

- Run `drova-voice cast --check` after extract.
- Run `drova-voice synth --engine fake` to synthesize without Fish.
- Run `drova-voice synth` to synthesize with Fish. That entry is out of scope for this map's cloud run.

## Driving it with control-drova-voice

Preconditions:

- Extract via `--manifest` has succeeded for this run.
- `control-drova-voice doctor` reports `ready: yes` and `fish_api_key: absent`.
- The harness refuses `synth` unless `--engine fake` is present.

- **Check the cast.** Run `control-drova-voice cli -- cast --check`. Exit code `0`. Stdout contains `melanie: 1` and `Sprecher ohne Stimme: keine`. It does not contain `Überbelegt` or `Gleiche Stimme`.
- **Synthesize.** Run `control-drova-voice cli -- synth --engine fake`. Exit code `0` and `network: clean` and `fake_worker_seen: yes`. Stdout contains `1 erzeugt (0 aus dem Cache, 1 neu erzeugt), 0 Fehler, 0 auffällige Dauer; übersprungen: player_choice: 1` and `Zeichen neu an fake gesendet: 33`. Stderr contains `fake: synth` and the sentence `Die Probe klingt klar und fertig.`
- **Confirm the cache.** Run `control-drova-voice snapshot --label after-synth`. `usage.jsonl` records `"engine": "fake"` and `"chars": 33`. `results.jsonl` has one ok row whose `wav` file exists and is non-empty. The choice id is not a result row.
- **Fish entry.** Do not run `drova-voice synth` without `--engine fake`. The harness returns exit `2`. Record that entry as not verified because it would send text to Fish.

## Gotchas

- `--engine` defaults to `fish`. A drive that omits `--engine fake` is a failed guard, not a fake-engine proof.
- `network: clean` must come from `network.txt`, backed by `strace.txt`: an `execve` of `workers/fake/worker.py` and no external `connect`. The flag on the command line does not prove the boundary.
- Text that contains `FAIL` makes the fake engine raise. The fixture must not contain that token.
- A second synth of the same line reports `1 aus dem Cache`. Do not delete the cache and then describe the second run as a fresh synthesis.
- `emote` is a separate user step and is not part of this cloud proof. The fake engine speaks the extracted sentence as-is.
