DrovaVoice {version}. English AI voices for Drova, Forsaken Kin.
================================================================

{origin_note}Unofficial fan mod. Free, not for sale.


FOR THE ENGLISH GAME
---------------------
For the English game language.
A saved AudioLanguage value in UserData\MelonPreferences.cfg wins.
Remove that key to use the language in Mods\DrovaVoice\Audio\language.txt from this zip.

{fixture_note}{library_note}
WHAT THE MOD DOES
-----------------
Characters speak their lines, and the subtitles keep running.
This zip voices {entries} lines. The audio folder is {language}.

Your own answer options, letters, and lines with quest or money values stay silent.
A line that still contains your player name stays silent. The name rules only strip German greetings.


REQUIREMENTS
------------
  - Drova, Forsaken Kin, Steam, Windows
  - MelonLoader 0.7.3
    https://github.com/LavaGang/MelonLoader/releases/tag/v0.7.3
  - Drova Modding API 0.5.4
    https://github.com/Drova-Modding/Drova-Modding-API/releases/tag/release-0.5.4
  - about 700 MB free


INSTALL
-------
Copy your game folder aside before you start.
In Steam, right-click the game, choose Manage, then Browse local files.

1. Install MelonLoader. Unzip MelonLoader.x64.zip 0.7.3 into the game folder so version.dll and the MelonLoader folder sit next to Drova.exe.
2. Install the Modding API. Unzip Modding_API.zip release-0.5.4 into the game folder.
3. Start the game once, reach the main menu, then quit.
4. Install this mod. Copy the Mods and UserLibs folders from this zip into the game folder and merge them with the folders already there.
5. Start the game.

You should then have:

  Drova - Forsaken Kin\
    Mods\DrovaVoice.dll
    Mods\DrovaVoice\Audio\language.txt
    Mods\DrovaVoice\Audio\{language}\index.json
    UserLibs\DrovaVoice.Core.dll
    UserLibs\NVorbis.dll


SETTINGS
--------
In the game options there is a DrovaVoice section for dialogue volume, your lines, and barks.
The same values are in UserData\MelonPreferences.cfg under DrovaVoice.
Enabled = false turns voicing off.


UNINSTALL
---------
Delete these from the game folder:
  Mods\DrovaVoice.dll
  Mods\DrovaVoice\
  UserLibs\DrovaVoice.Core.dll
  UserLibs\NVorbis.dll if no other mod needs it

Remove MelonLoader and the Modding API the way their own guides describe.


LIMITS
------
  - The mod has not been played through the whole game. A character can get the wrong voice.
  - The voices are AI. Stress and names can sound wrong.
  - Do not run DrovaTTS at the same time. This mod writes a warning to the log.
  - After a game update, new or changed lines can stay silent.


PROBLEMS
--------
For a wrong voice, the wrong gender, or a bug, open an issue at https://github.com/janphi001/DrovaTTAI/issues
Include the character, the place in the game, and the log.

The mod writes MelonLoader\Latest.log in the game folder.
Lines with DrovaVoice show whether the mod loaded and whether something failed.

Licenses and the voice list are in LIZENZEN.txt
