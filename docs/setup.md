# Setup Spiel & Mod

Getestet mit: Drova: Forsaken Kin (Steam, Stand 2026-10), Unity 2022.3.45f1, MelonLoader 0.7.3, Drova Modding API 0.5.4.

1. `MelonLoader.x64.zip` (v0.7.3) in den Spielordner entpacken.
2. `Modding_API.zip` (release-0.5.4) in den Spielordner entpacken (`Mods/`, `UserLibs/`).
3. Spiel einmal bis ins Hauptmenü starten (erzeugt `MelonLoader/Il2CppAssemblies`), beenden.
4. Mod bauen: `dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release` (kopiert nach `Mods/` und `UserLibs/`).
   Anderer Spielpfad: Umgebungsvariable `DROVA_GAME_DIR` setzen.

Rückbau: `version.dll`, `MelonLoader/`, `Mods/`, `UserLibs/`, `Plugins/` (falls angelegt) aus dem Spielordner löschen.
