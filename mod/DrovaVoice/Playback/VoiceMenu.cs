using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Drova_Modding_API.Access;
using Il2CppCustomFramework.Localization;
using MelonLoader;

namespace DrovaVoice.Playback
{
    /// <summary>Panel „Drova Voice“ im Optionsmenü des Spiels. Texte deutsch, für jede Spielsprache registriert.</summary>
    internal sealed class VoiceMenu
    {
        private const string ModName = "DrovaVoice";
        private readonly VoiceService _service;
        private readonly MelonLogger.Instance _log;
        private bool _registered, _panelFailed;
        private readonly HashSet<string> _logged = new HashSet<string>();

        public VoiceMenu(VoiceService service, MelonLogger.Instance log) { _service = service; _log = log; }

        private static readonly (string Key, string Text)[] Texts =
        {
            ("title", "Drova Voice"),
            ("note", "Lautstärke der KI-Stimmen. Über 100 % wird verstärkt. Änderungen gelten ab der nächsten gesprochenen Zeile."),
            ("enabled", "Vertonung"), ("on", "An"), ("off", "Aus"),
            ("dialog", "Dialog-Lautstärke (%)"), ("player", "Spieler-Lautstärke (%)"), ("bark", "Bark-Lautstärke (%)"),
            ("barkMin", "Barks: volle Lautstärke bis (Meter)"), ("barkMax", "Barks: stumm ab (Meter)"),
        };

        public void Register()
        {
            if (_registered) return;
            try
            {
                RegisterTexts();
                OptionMenuAccess.Instance.OnOptionMenuOpen += new OptionMenuAccess.OptionMenuAction(OnOpen);
                OptionMenuAccess.Instance.OnOptionMenuClose += new OptionMenuAccess.OptionMenuAction(OnClose);
                _registered = true;
            }
            catch (Exception e) { Fail("Registrierung", e); }
        }

        private void RegisterTexts()
        {
            var entries = new List<LocalizationAccess.LocalizationEntry>();
            // Die API schreibt je Sprache eine .loc-Datei in Drova_Data/StreamingAssets/Localization/<Sprache>/; nur vorhandene Ordner bedienen
            // (sonst loggt sie für jede fehlende Sprache einen Fehler). Die Namen der Enum-Werte entsprechen den Ordnernamen.
            string locRoot = System.IO.Path.Combine(MelonLoader.Utils.MelonEnvironment.GameRootDirectory, "Drova_Data", "StreamingAssets", "Localization");
            foreach (var language in Enum.GetValues(typeof(LocalizationDB.ELanguage)))
                if (System.IO.Directory.Exists(System.IO.Path.Combine(locRoot, language.ToString()!)))
                foreach (var (key, text) in Texts)
                    entries.Add(new LocalizationAccess.LocalizationEntry(key, text, (LocalizationDB.ELanguage)language));
            LocalizationAccess.CreateLocalizationEntries(entries, ModName);
        }

        private void OnOpen()
        {
            if (_panelFailed) return;
            try
            {
                var builder = OptionMenuAccess.Instance.GetBuilder(ModName);
                // Die API gibt für eine schon verwendete ID keinen zweiten Builder zurück (null). Nach einem Szenenwechsel ist das Fenster neu
                // und die ID wieder frei: dann wird das Panel neu gebaut. Darum gibt es bewusst keinen eigenen „gebaut“-Merker.
                if (builder == null) return;
                var s = _service.Settings;
                builder.CreateHeader(LocalizationAccess.GetLocalizedString(ModName, "title"))
                       .CreateDisclaimer(LocalizationAccess.GetLocalizedString(ModName, "note"))
                       .CreateSwitch(LocalizationAccess.GetLocalizedString(ModName, "enabled"), LocalizationAccess.GetLocalizedString(ModName, "on"), LocalizationAccess.GetLocalizedString(ModName, "off"), MenuKeys.Enabled, s.Enabled, false)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "dialog"), MenuKeys.DialogVolume, 0, 200, s.DialogPercent)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "player"), MenuKeys.PlayerVolume, 0, 200, s.PlayerPercent)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "bark"), MenuKeys.BarkVolume, 0, 200, s.BarkPercent)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "barkMin"), MenuKeys.BarkMinDistance, 0, (int)VoiceSettings.MaxBarkDistance, (int)s.BarkMinDistance)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "barkMax"), MenuKeys.BarkMaxDistance, 1, (int)VoiceSettings.MaxBarkDistance, (int)s.BarkMaxDistance)
                       .Build();
            }
            catch (Exception e) { _panelFailed = true; Fail("Panel", e); }
        }

        private void OnClose()
        {
            try { LoadFromConfig(); }
            catch (Exception e) { Fail("Werte lesen", e); }
        }

        /// <summary>Liest die Menüwerte aus der Spielkonfiguration (fehlende bleiben null) und wendet sie an.</summary>
        public void LoadFromConfig()
        {
            var values = new MenuValues(
                ReadBool(MenuKeys.Enabled), ReadInt(MenuKeys.DialogVolume), ReadInt(MenuKeys.PlayerVolume), ReadInt(MenuKeys.BarkVolume),
                ReadInt(MenuKeys.BarkMinDistance), ReadInt(MenuKeys.BarkMaxDistance));
            var warnings = new List<string>();
            var next = _service.BaseSettings.WithOverrides(values, warnings);   // Datei-Einstellungen als Grundlage: ein fehlender Schlüssel fällt auf den Dateiwert zurück
            foreach (string w in warnings) if (_logged.Add("w|" + w)) _log.Warning("Optionsmenü: " + w);   // dieselbe Warnung nur einmal
            var change = _service.Apply(next);
            if (change != SettingsChange.None)
                _log.Msg($"Optionsmenü: {change}; Dialog {next.DialogPercent} %, Spieler {next.PlayerPercent} %, Barks {next.BarkPercent} %, Reichweite {next.BarkMinDistance}–{next.BarkMaxDistance}, {(next.Enabled ? "an" : "aus")}.");
        }

        private static int? ReadInt(string key) => ConfigAccessor.TryGetConfigValue<int>(key, out var v) ? v : (int?)null;
        private static bool? ReadBool(string key) => ConfigAccessor.TryGetConfigValue<bool>(key, out var v) ? v : (bool?)null;

        private void Fail(string what, Exception e)
        {
            if (!_logged.Add(what)) return;
            _log.Warning($"Optionsmenü ({what}): {e.GetType().Name}: {e.Message}. Die Einstellungen aus MelonPreferences.cfg gelten weiter.");
        }
    }
}
