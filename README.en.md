# DrovaVoice (DrovaTTAI)

[Deutsch](README.md) · **English**

AI voices for **Drova – Forsaken Kin**. Characters speak their dialogue, and the subtitles run as usual.

The project has two parts:

- **Generator** (`generator/`, Python, command `drova-voice`): reads the dialogue from your own game installation and turns it into audio files.
- **Mod** (`mod/`, C#, MelonLoader): plays those files in the game.

## Download or make your own

**All voices are AI-generated.**

- **German, ready to play:** the package with the mod and all German audio files is on the [Releases](https://github.com/janphi001/DrovaTTAI/releases/latest) page. Download it, copy it into the game folder, play. The install guide is `README.txt` inside the ZIP (in German; the short version is below).
- **Another language:** the game ships text in German, English, Spanish, French, Polish, Korean and Chinese. With the generator in this repo you can create the voices for any of these yourself. Follow the guide below with the changes from [Other languages](#other-languages).

This repo itself contains **no game text and no audio**. Both are created locally from your copy of the game and are not in git (`data/`, `cache/`, `out/` are excluded).

Status: all 245 named speakers have a voice, and about 13,800 lines are voiced in German (41 voices plus 7 variants such as old woman, giant, dwarf). On top of that come barks (remarks in the world, with their own volume, getting quieter with distance) and lines of generic characters (`NPC`, guard …): for those, the mod picks a fixed voice per character from a small pool by gender. Not voiced: the player's answer options (as in the original), letters, and lines with quest or money values. Lines with the player's name are spoken without the name.

### Installing the German release (short version)

1. Install [MelonLoader 0.7.3](https://github.com/LavaGang/MelonLoader/releases/tag/v0.7.3): unzip `MelonLoader.x64.zip` into the game folder, next to `Drova.exe`.
2. Install the [Drova Modding API 0.5.4](https://github.com/Drova-Modding/Drova-Modding-API/releases/tag/release-0.5.4): unzip `Modding_API.zip` into the game folder.
3. Start the game once until the main menu, then quit.
4. Copy the `Mods` and `UserLibs` folders from the DrovaVoice ZIP into the game folder (merge, don't replace).
5. Start the game.

To uninstall, delete `Mods/DrovaVoice.dll`, `Mods/DrovaVoice/` and `UserLibs/DrovaVoice.Core.dll` (and `UserLibs/NVorbis.dll` if no other mod needs it).

## Speech synthesis: Fish Audio

The voices are made with **[Fish Audio](https://fish.audio)** (model `s2.1-pro-free`). I chose Fish because API use is free for developers and the quality for German and for emotions in the text was convincing. That is the state during development (October 2026); Fish can change prices and limits at any time. Check your account before a full run.

According to the Fish changelog, `s2.1-pro-free` is the same model as `s2.1-pro` and free until **30 Nov 2026**. After that, the price list shows `s2.1-pro` at 15 USD per million UTF-8 bytes. The model ID is set in one place: `fish_model` in `generator/config.yaml`, otherwise the environment variable `FISH_MODEL`, otherwise `s2.1-pro-free`. The cache key contains the model (`fish-audio/<id>`) and every deviation from the defaults for language (`de`), latency (`normal`), `temperature` and `top_p` (both `0.7`). With the defaults, the existing cache stays valid. A change misses every existing WAV; `synth` then stops and only regenerates after `synth --accept-model-change`. If you keep an ID Fish no longer knows, the request silently falls back to `s2.1-pro` according to the TTS docs and is billed, without the cache key changing.

Good to know:

- Fish is a **cloud service**. The spoken text of every line is sent to `api.fish.audio`. Fish's terms apply.
- You need your own Fish account and an **API key**. The key never goes into a file or into git. The generator only reads it from the environment variable `FISH_API_KEY`.
- The voices in `casting/fish_voices.yaml` are official German Fish voices and voices from the public Fish library. **Library voices by community authors are for non-commercial use only.** The generated audio files must not be sold.
- A local fallback (Kitten TTS) is prepared but sounds clearly worse. Reasoning: `docs/decisions/2026-10-tts-engine.md`.

## Requirements

| What | For |
|---|---|
| Windows, Drova: Forsaken Kin (Steam) | Game and mod (tested with the October 2026 build, Unity 2022.3.45) |
| [MelonLoader](https://github.com/LavaGang/MelonLoader) 0.7.3 and the Drova Modding API 0.5.4 | Mod framework in the game |
| [.NET SDK](https://dotnet.microsoft.com/download) | Building the mod |
| Python 3.11 or newer, ideally with [uv](https://docs.astral.sh/uv/) | Generator |
| [ffmpeg](https://ffmpeg.org/) and ffprobe on the `PATH`, ffmpeg with `libvorbis` (the variants also need `rubberband`) | Encoding audio |
| Fish account with an API key | Generating voices |
| About 1 GB of free space | The finished audio files take about 550 MB, plus intermediate files |

Make a copy of your game folder before installing. How to remove the mod completely is described in `docs/setup.md`.

## Guide

All commands are written for Git Bash. Replace the game path with your own.

### 1. Get the repo

```bash
git clone https://github.com/janphi001/DrovaTTAI.git
cd DrovaTTAI
```

### 2. Put MelonLoader and the Modding API into the game

1. Unzip `MelonLoader.x64.zip` (v0.7.3) into the game folder, so that `version.dll` and the `MelonLoader/` folder sit next to the game EXE.
2. Unzip `Modding_API.zip` (release-0.5.4) into the game folder as well (this creates `Mods/` and `UserLibs/`).
3. Start the game once until the main menu and quit again. MelonLoader creates the files under `MelonLoader/Il2CppAssemblies` on the way.

More, including removal: `docs/setup.md`.

### 3. Build the mod

The game must be **closed**. The build only copies the mod into the game folder when `DeployToGame` is set. Without it, it only compiles.

```bash
dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release -p:DeployToGame=true
```

If the game is not in the default location, set the environment variable `DROVA_GAME_DIR` to the game folder first.

### 4. Export the dialogue from the game

The mod can write the game's dialogue trees to a file. This export contains game text, so it stays on your machine.

1. Start the game and stay **in the main menu**, with the game window in front. Don't load a save.
2. In the game folder, create an empty file `Mods/DrovaVoice/export.trigger`. The mod picks it up, deletes it and writes the results to `Mods/DrovaVoice/Export/<language>/`.
3. Wait until the export message appears in the log (`MelonLoader/Latest.log`), then **quit the game**. An export in the main menu disables voicing for that session, so never keep playing right after it.
4. Also create `export-npcs.trigger` the same way. It produces the list of speakers and voices.

Details and known quirks: `docs/export.md`.

### 5. Set up the generator

```bash
cd generator
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
cp config.example.yaml config.yaml
```

In `generator/config.yaml`, enter the path to your game folder (`game_dir`, with `/` instead of `\`) and the language (`language: de`).

Then fetch the export from the game into the work folder and check it:

```bash
.venv/Scripts/drova-voice export fetch
.venv/Scripts/drova-voice export report --manifest ../data/export/de/manifest-loaded.json
```

### 6. Set the Fish key

You get the key in your Fish account. Set it for the current shell only:

```bash
export FISH_API_KEY="your-key"
```

Never store it in a file. If it ever shows up somewhere by accident (chat, log, git), reset it at Fish right away.

### 7. Generate the voices

The generator works in steps and can be stopped and resumed at any time (finished lines are not computed again). A single speaker is a good first test:

```bash
cd generator
.venv/Scripts/drova-voice extract
.venv/Scripts/drova-voice cast --check --npc Adela
.venv/Scripts/drova-voice emote --npc Adela
.venv/Scripts/drova-voice synth --npc Adela      # sends the text to Fish
.venv/Scripts/drova-voice encode --npc Adela
.venv/Scripts/drova-voice install --npc Adela    # copies into the game (--prune deletes orphaned OGG)
.venv/Scripts/drova-voice report --npc Adela
```

`extract` reads `data/export/<language>/manifest.json`. If that file is missing, it uses `manifest-loaded.json` (the result of `export.trigger`).

Start the game, load a save, talk to Adela: you should hear her voice. `synth --limit 20` only creates the first 20 lines for testing. `synth --limit 0` sends nothing to Fish.

**All characters at once** (casting and full run):

```bash
.venv/Scripts/drova-voice cast --propose         # assign voices automatically
.venv/Scripts/drova-voice batches                # split into stages by importance
.venv/Scripts/drova-voice synth --batch 1
.venv/Scripts/drova-voice encode --batch 1
.venv/Scripts/drova-voice install --batch 1
.venv/Scripts/drova-voice report --by-speaker    # gaps per speaker
```

Repeating this for all stages takes hours and sends about 850,000 characters to Fish. The character count is shown at the end of every `synth` run. On credit, limit or login errors, `synth` stops cleanly after five failures in a row. You can simply continue later.

All steps and options: `docs/generator.md`. The audio file format: `docs/audio-format.md`.

`drova-voice package` builds a ZIP for players from the game folder (mod, libraries, the indexed audio, `README.txt` and `LIZENZEN.txt` from `release/`), the same way the German release was made.

`drova-voice package --language en` builds `DrovaVoice-<version>-en.zip` from `Mods/DrovaVoice/Audio/en` and writes `language.txt` with `en`. With no game audio, `drova-voice package --language en --fixture` builds that zip from one invented line, "The crate is empty." That zip is a packaging fixture. `DrovaVoice-<version>-en.synth-gap.txt` next to the zip lists what still needs synth. `data/export/en/manifest.json` is absent. `casting/fish_voices.yaml` has no `region: en`. The greetings in `player_name.py` are German. `data/lines.jsonl`, `data/synth/results.jsonl`, and `data/encoded.jsonl` are shared. Fish reads `FISH_API_KEY` from the environment.

### 8. Play and adjust

Start the game, load a save, talk to NPCs. The settings are in `<game>/UserData/MelonPreferences.cfg` in the `[DrovaVoice]` section. Values in the file apply after a restart. Volume, bark distance and the on/off switch in the options menu apply from the next line on.

| Key | Default | Meaning |
|---|---|---|
| `Enabled` | `true` | Voicing on or off |
| `DialogVolume` | `100` | Volume of NPC voices in percent (0 to 200) |
| `PlayerVolume` | `100` | Volume of player lines in percent (0 to 200) |
| `BarkVolume` | `100` | Volume of world remarks in percent (0 to 200) |
| `BarkMinDistance` | `15` | Barks: full volume up to this distance in world meters |
| `BarkMaxDistance` | `120` | Barks: silent from this distance on, linearly quieter in between |
| `BarkProbe` | `false` | Development: log the character of every statement |
| `AudioLanguage` | `de` | Subfolder under `Mods/DrovaVoice/Audio` |
| `CacheMB` | `64` | Memory for loaded voice clips (8 to 512) |
| `Diagnostics` | `false` | Detailed log, helps with troubleshooting |
| `ExportLanguage` | `de` | Folder name of the export |

More notes, log messages and the acceptance checklist: `docs/playback.md` (German).

The mod reloads a new or changed `index.json` while the game is running (about once per second, based on the file's size and write time). To reload the same file without a change in size or time, create an empty file `Mods/DrovaVoice/reload.trigger`. If loading fails, the reason is in `MelonLoader/Latest.log`; a previously valid index stays active.

## Other languages

The guide above works for every language of the game. The folder names are `de`, `en`, `es`, `fr`, `pl`, `ko`, `zh_CN` and `zh_TW`. For a language other than German, change the following, here using English (`en`) as the example:

1. **Switch the game to the language** and set `ExportLanguage = "en"` and `AudioLanguage = "en"` in the `[DrovaVoice]` section of `UserData/MelonPreferences.cfg`. Then trigger the export again (step 4): it goes to `Mods/DrovaVoice/Export/en/`.
2. **Switch the generator to the language:** `language: en` in `generator/config.yaml`. With that, `extract` reads the English text, numbers are spelled out in English, Fish gets `language=en`, and `install` writes to `Mods/DrovaVoice/Audio/en/`.
3. **Pick voices in that language:** the 41 voices in `casting/fish_voices.yaml` are German voices. Look for voices in your language in the [Fish library](https://fish.audio) and add them there (`id`, `label`, `gender`, `age`). Then adjust `casting/casting.yaml` or reassign with `drova-voice cast --propose`. The character profiles (`casting/profiles.jsonl`) apply to every language.
4. **Then as usual:** `extract`, `emote`, `synth`, `encode`, `install`.

Pack the result with `drova-voice package --language en`. With no game audio, add `--fixture`. The leftovers are the same ones named next to the package command above.

Good to know:

- The emotions in `casting/emotions.jsonl` were derived from the German text. They are keyed by line ID, so they apply to other languages too; German emphasis words that don't appear in the text are skipped.
- Lines with the player's name are spoken without the name. The rules for that are tuned to German; in other languages a stray comma or form of address may be left over.
- For Chinese and Korean, the generator does not spell out numbers; the digits go to Fish, which reads them out based on `language`.
- The pronunciation lexicon `casting/lexicon.yaml` is empty and applies to all languages. Add names there that Fish pronounces wrong.

If you make a set for another language, feel free to open an issue. Other players can then find it.

## Compatibility

**[DrovaTTS](https://github.com/Raster96/DrovaTTS)** (Nexus: drovaforsakenkin/mods/30) and DrovaVoice replace the same dialogue connector of the Modding API. With both mods installed, the last call wins; the other stays silent without the game showing an error. DrovaTTS registers in MelonLoader as "Drova TTS", and its assembly is called `DrovaTTS`.

DrovaVoice checks this at startup, in the MelonLoader mod list and the loaded assemblies. If either matches, it writes a warning to the log (`MelonLoader/Latest.log`, the text starts with `DrovaTTS ist geladen`). Don't use both mods together. Remove one of them and restart the game.

Quieter music while voices play (ducking) is only an idea and not built here. The mod does not change the music.

## Voices used

The project uses **41 Fish voices** and **7 variants**. All of them are listed with their Fish IDs in `casting/fish_voices.yaml`; here is the overview. I picked them after listening to samples. Imitations of real people were excluded up front.

- **8 official German Fish voices** (Lena, Leon, Melanie, Lukas from Austria, Emma, Elin from Switzerland, Jonas, Valentina from Austria)
- **33 voices from the public Fish library** (community authors; **non-commercial use only**)

| Key | Name at Fish | Gender | Origin | Age | Source | Fish ID |
|---|---|---|---|---|---|---|
| `lena` | Lena | female | Germany |  | official (Fish) | `3937b44b604249f18b94913daef94043` |
| `leon` | Leon | male | Germany |  | official (Fish) | `7b7c88bf825a4ab3bca27d55c26ddf16` |
| `melanie` | Melanie | female | Germany |  | official (Fish) | `d979e92f9c8a489fa581f55f6b9e48da` |
| `lukas` | Lukas (Österreich) | male | Austria |  | official (Fish) | `c1e7cc926aa5469aa966c353094d4b0b` |
| `emma` | Emma | female | Germany |  | official (Fish) | `3235abc9a84b407d92f73539a5651720` |
| `elin` | Elin (Schweiz) | female | Switzerland |  | official (Fish) | `0b96bf70a20d47f6b9e825d9cfe0e8c8` |
| `jonas` | Jonas | male | Germany |  | official (Fish) | `44f1ec96a51e429f8b87776cbc55a997` |
| `valentina` | Valentina (Österreich) | female | Austria |  | official (Fish) | `e5fb46af69e0481fa0d2d0f209b07ae2` |
| `ben_9e3f0e` | Ben | male | Germany | young | library (community) | `9e3f0ea9a0a44c4d9f0c422715d0229f` |
| `ben_9e0a50` | Ben | male | Germany | young | library (community) | `9e0a50728a424b048575d286a79c42be` |
| `schales_7ef3ea` | Schales | male | Germany | young | library (community) | `7ef3eae2ff754f398e90dbcafdb7c5c8` |
| `vorlesen_stimlagen_90042f` | Vorlesen Stimlagen | male | Germany | middle-aged | library (community) | `90042f762dbf49baa2e7776d011eee6b` |
| `german_d83fad` | German | male | Germany | middle-aged | library (community) | `d83fade735f4447698a08986de772c82` |
| `ben_a20517` | Ben | male | Germany | middle-aged | library (community) | `a20517d0d23048319e4ced960899187e` |
| `bao_de2_chau_e89195` | Bao DE2 Chau | male | Germany | middle-aged | library (community) | `e891954162584409bce5cf43aebd1726` |
| `german_wisdom_m_3130ae` | GERMAN WISDOM. M | male | Germany | middle-aged | library (community) | `3130ae7c3d844e2998978289c7c11c98` |
| `germany_d5f684` | GERMANY | male | Germany | middle-aged | library (community) | `d5f6842c9bc849408c4b6c2a51a1c044` |
| `deutscheman_voice_fur_ti_9c0305` | Deutscheman_voice_fur_tiktok | male | Germany | middle-aged | library (community) | `9c03054b93ee4eda8c1db08767fd8d45` |
| `adam_570cf0` | Adam | male | Germany | middle-aged | library (community) | `570cf019f1044c3cb2917553fdfa9d34` |
| `almanca_i_yi_ses_7d4cbb` | ALMANCA İYİ SES | male | Germany | middle-aged | library (community) | `7d4cbb1b490744e4a5b4bad4759ff751` |
| `german_father_c07993` | German Father | male | Germany | old | library (community) | `c079932b47564fcfad0a9f6874a49df7` |
| `father_german_usama_14ccc0` | father German Usama | male | Germany | old | library (community) | `14ccc066ad16414487b60195328eed29` |
| `p0_2765f2` | P0 | male | Germany | old | library (community) | `2765f263701044409059e23206bdd47f` |
| `erz_hler_c23420` | Erzähler | male | Germany | old | library (community) | `c2342039ff8248d4a335e5cc2091d40d` |
| `niko_ba082d` | niko | male | Germany | old | library (community) | `ba082dea53e841aeb420dc612cb804ed` |
| `deep_783f5c` | DEEP | male | Germany | old | library (community) | `783f5c7cb4f64ef48a7c7f5166bbdc01` |
| `emilia_german_194b99` | EMILIA GERMAN | female | Germany | young | library (community) | `194b99d7c27e462ea40694cddf1f7c96` |
| `natasha_deutsch_88b185` | Natasha Deutsch | female | Germany | young | library (community) | `88b185f908c04ebea8b6ff642c8fea82` |
| `tea_capcut_044275` | Tea (capcut) | female | Germany | young | library (community) | `04427518d0a043ae825b5185515882b5` |
| `frau_110e73` | Frau | female | Germany | young | library (community) | `110e739143fc4607a1754ba1b24d55cb` |
| `douchland_old_story_2ef205` | Douchland OLD STORY | female | Germany | young | library (community) | `2ef205fde3f9475eaf908f87736cafec` |
| `catrinja_c5b66a` | Catrinja | female | Germany | middle-aged | library (community) | `c5b66a80d90749fc914c714e793d1a2f` |
| `deutsche_ansagestimme_a586d5` | Deutsche Ansagestimme | female | Germany | middle-aged | library (community) | `a586d5007b0249f0b25f32a036b1713c` |
| `said_deb281` | said | female | Germany | middle-aged | library (community) | `deb28100c45547c8871753ab1fdf9856` |
| `amira_german_b59d11` | Amira - German | female | Germany | middle-aged | library (community) | `b59d1164746a48bf971f4a0fd2cbf814` |
| `almanca_yeni_22d4f9` | almanca yeni | female | Germany | middle-aged | library (community) | `22d4f9243101493a82ad8d27694a2038` |
| `pia_87bebc` | Pia | female | Germany | old | library (community) | `87bebc5ad62a4deaaf254befad582453` |
| `lebhafte_junge_frau_37bab8` | Lebhafte junge Frau | female | Germany | young | library (community) | `37bab8e91a5a44fa853b41bc6a8730e8` |
| `m_dchen_6761f7` | mädchen | female | Germany | young | library (community) | `6761f7ebcbce46db89864f9ce0a2d242` |
| `kind_von_oben_578878` | Kind von oben | female | Germany | child | library (community) | `57887823e98a48e0a7c01819628ba59b` |
| `warmer_junger_mann_179999` | Warmer junger Mann | male | Germany | young | library (community) | `1799997c77204a1b8753511fdf47f485` |

Empty age fields mean: not given for the official voices. The Fish ID is the voice's identifier at Fish (also in the API). The library has no guaranteed lifetime: the author can delete or hide a voice, Fish can take it down, and `GET /model/{id}` then returns 404. Before a full run, `drova-voice cast --check-voices` checks the IDs the casting actually uses. Without `FISH_API_KEY` the command skips the check and makes no request. You can add a replacement under `fallbacks:` in `casting/fish_voices.yaml` (`voice: other_voice`). The check names it; `synth` does not switch on its own.

### Variants

For characters without a fitting voice, `encode` reshapes a base voice with ffmpeg (`rubberband`): pitch, timbre and tempo.

| Key | Base voice | Used for |
|---|---|---|
| `alte_frau` | `pia_87bebc` | old women |
| `alte_frau_rau` | `amira_german_b59d11` | old women, rougher |
| `riese` | `deep_783f5c` | giants (deep, slow) |
| `zwerg` | `erz_hler_c23420` | dwarves (brighter timbre) |
| `schurke_hell` | `german_d83fad` | bright-voiced villains |
| `jugendlicher` | `ben_9e3f0e` | teenagers |
| `knabe` | `schales_7ef3ea` | boys |

### Who speaks with which voice

- **Automatic:** `drova-voice cast --propose` assigns a voice to all 245 named speakers based on profiles (gender, age, type, in `casting/profiles.jsonl`) and writes the result to `casting/casting_auto.yaml`. Each voice is spread over several characters (most often 7 to 8 per voice).
- **By hand** (`casting/casting.yaml`, takes precedence): Adela `melanie`, Jero `german_wisdom_m_3130ae`, Enya `lena`, Femke `schales_7ef3ea`, Gerion `lukas`, Gilwar `jonas`, Jola `emma`, Meluna `valentina`, Reija `lebhafte_junge_frau_37bab8`.
- **Player:** the fixed voice `leon` for all player lines.
- **Still missing:** real children's voices (only `kind_von_oben_578878` and the `knabe` variant), more old women's voices and bright male voices.

## Adjusting voices

- **Casting:** `casting/casting.yaml` (by hand) takes precedence over the automatic `casting/casting_auto.yaml`. Entry: `Name: {voice: key}`. The available keys are in `casting/fish_voices.yaml`, including the variants.
- **Regenerate one line or character:** delete the matching WAV in `cache/synth/`, then repeat `synth`, `encode` and `install` for that speaker.
- **Your own voice:** Fish can clone a voice from a short recording. Recording tips: `docs/stimmaufnahme.md` (German).

## Troubleshooting

| Problem | Fix |
|---|---|
| No voices in the game | Check `MelonLoader/Latest.log`: does it say `Audio-Connector der Modding API ersetzt.` (only after loading a save)? Is there a `Mods/DrovaVoice/Audio/<language>/index.json`? If it says `DrovaTTS ist geladen`, DrovaTTS is installed too; remove one of the two mods |
| New lines missing after `install` | The mod reloads `index.json` when its size or write time changes, or via `reload.trigger`. The log says `Index neu geladen` or shows an error (`Index nicht nutzbar` / `Index nicht neu geladen`) |
| Export produces nothing | Trigger it in the main menu with the window in front, then quit the game (`docs/export.md`) |
| `synth` stops | Check Fish credit, limit or key, then run the command again |
| Build fails | Close the game, check the path (`DROVA_GAME_DIR`) |
| Wrong voice or gender | Please [open an issue](https://github.com/janphi001/DrovaTTAI/issues) with the character, the place in the game and `MelonLoader/Latest.log` |

## More documentation

The detailed docs are in German:

- Design: `docs/superpowers/specs/2026-10-10-drova-voice-design.md`
- Status and decisions: `docs/HANDOFF.md`, `docs/decisions/`
- Setting up game and mod: `docs/setup.md`, export: `docs/export.md`
- Generator: `docs/generator.md`, playback: `docs/playback.md`, file format: `docs/audio-format.md`

## Legal

The code is under the [MIT license](LICENSE). That covers only the code in this repo. *Drova – Forsaken Kin* and its text belong to its developers and publisher; this project is an unofficial fan mod and not affiliated with them. The voices come from Fish Audio and are subject to Fish's terms and the licenses of the individual voices (see above).
