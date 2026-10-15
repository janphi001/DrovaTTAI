# Agent rules

CI (`.github/workflows/checks.yml`) runs the commands in this table. The checks fail when the rule is broken. Skipping this file does not skip them.

| Rule | What enforces it |
| --- | --- |
| Commit subjects are English and imperative, with no Co-Authored-By or other Claude trailer | `python3 tools/checks/commit_messages.py` |
| Do not add real Drova dialogue lines. Use a short invented fixture. | `python3 tools/checks/no_game_dialogue.py` |
| A build of mod/DrovaVoice does not copy into the game folder unless `-p:DeployToGame=true` | `DeployToGame` in `mod/DrovaVoice/DrovaVoice.csproj`, locked by `python3 tools/checks/no_deploy_on_build.py` |
| Player choice lines stay silent | `python3 tools/checks/player_choice_silent.py` |
| Do not store a Fish API key, leak it through errors or redirects, or call Fish outside the worker | `python3 tools/checks/fish_key.py` |
