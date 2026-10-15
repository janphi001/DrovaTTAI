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
        private bool _registered, _built, _failed;

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
            foreach (var language in Enum.GetValues(typeof(LocalizationDB.ELanguage)))
                foreach (var (key, text) in Texts)
                    entries.Add(new LocalizationAccess.LocalizationEntry(key, text, (LocalizationDB.ELanguage)language));
            LocalizationAccess.CreateLocalizationEntries(entries, ModName);
        }

        private void OnOpen()
        {
            if (_built || _failed) return;
            try
            {
                var builder = OptionMenuAccess.Instance.GetBuilder(ModName);
                if (builder == null) return;   // die API gibt für eine schon verwendete ID keinen zweiten Builder zurück
                var s = _service.Settings;
                builder.CreateHeader(LocalizationAccess.GetLocalizedString(ModName, "title"))
                       .CreateDisclaimer(LocalizationAccess.GetLocalizedString(ModName, "note"))
                       .CreateSwitch(LocalizationAccess.GetLocalizedString(ModName, "enabled"), LocalizationAccess.GetLocalizedString(ModName, "on"), LocalizationAccess.GetLocalizedString(ModName, "off"), MenuKeys.Enabled, s.Enabled, false)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "dialog"), MenuKeys.DialogVolume, 0, 200, s.DialogPercent)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "player"), MenuKeys.PlayerVolume, 0, 200, s.PlayerPercent)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "bark"), MenuKeys.BarkVolume, 0, 200, s.BarkPercent)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "barkMin"), MenuKeys.BarkMinDistance, 0, 200, (int)s.BarkMinDistance)
                       .CreateSlider(LocalizationAccess.GetLocalizedString(ModName, "barkMax"), MenuKeys.BarkMaxDistance, 10, 400, (int)s.BarkMaxDistance)
                       .Build();
                _built = true;
            }
            catch (Exception e) { Fail("Panel", e); }
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
            var next = _service.Settings.WithOverrides(values, warnings);
            foreach (string w in warnings) _log.Warning("Optionsmenü: " + w);
            var change = _service.Apply(next);
            if (change != SettingsChange.None)
                _log.Msg($"Optionsmenü: {change}; Dialog {next.DialogPercent} %, Spieler {next.PlayerPercent} %, Barks {next.BarkPercent} %, Reichweite {next.BarkMinDistance}–{next.BarkMaxDistance}, {(next.Enabled ? "an" : "aus")}.");
        }

        private static int? ReadInt(string key) => ConfigAccessor.TryGetConfigValue<int>(key, out var v) ? v : (int?)null;
        private static bool? ReadBool(string key) => ConfigAccessor.TryGetConfigValue<bool>(key, out var v) ? v : (bool?)null;

        private void Fail(string what, Exception e)
        {
            if (_failed) return;
            _failed = true;
            _log.Warning($"Optionsmenü ({what}): {e.GetType().Name}: {e.Message}. Die Einstellungen aus MelonPreferences.cfg gelten weiter.");
        }
    }
}
