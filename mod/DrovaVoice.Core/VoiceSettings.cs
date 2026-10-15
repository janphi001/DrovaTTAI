using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>Validierte Einstellungen aus MelonPreferences. Ungültige Werte werden begrenzt und als Warnung zurückgemeldet.</summary>
    public sealed class VoiceSettings
    {
        public const int MinCacheMegabytes = 8;
        public const int MaxCacheMegabytes = 512;
        public const string DefaultLanguage = "de";
        private const int MaxLanguageLength = 16;

        private VoiceSettings() { }

        public bool Enabled { get; private set; }
        public int DialogPercent { get; private set; }
        public int PlayerPercent { get; private set; }
        public int BarkPercent { get; private set; }
        public float BarkMinDistance { get; private set; }
        public float BarkMaxDistance { get; private set; }
        public const float DefaultBarkMinDistance = 15f;
        public const float DefaultBarkMaxDistance = 120f;
        public const float MaxBarkDistance = 500f;
        public string Language { get; private set; } = DefaultLanguage;
        public int CacheMegabytes { get; private set; }
        public bool Diagnostics { get; private set; }
        public long CacheBytes => CacheMegabytes * 1024L * 1024L;

        public int PercentFor(VoiceCategory category) => category switch
        {
            VoiceCategory.Player => PlayerPercent,
            VoiceCategory.Bark => BarkPercent,
            _ => DialogPercent,
        };

        public static VoiceSettings Create(bool enabled, int dialogPercent, int playerPercent, string? language,
                                           int cacheMegabytes, bool diagnostics, List<string> warnings, int barkPercent = 100,
                                           float barkMinDistance = DefaultBarkMinDistance, float barkMaxDistance = DefaultBarkMaxDistance)
        {
            if (barkMinDistance < 0f)
            {
                warnings.Add($"BarkMinDistance = {barkMinDistance} darf nicht negativ sein; verwende 0.");
                barkMinDistance = 0f;
            }
            if (barkMinDistance > MaxBarkDistance || barkMaxDistance > MaxBarkDistance)
            {
                bool infinite = float.IsInfinity(barkMinDistance) || float.IsInfinity(barkMaxDistance);
                warnings.Add($"Bark-Reichweite {barkMinDistance}–{barkMaxDistance} liegt über {MaxBarkDistance}; " + (infinite ? $"verwende {DefaultBarkMinDistance}–{DefaultBarkMaxDistance}." : $"begrenze auf {MaxBarkDistance}."));
                if (infinite) { barkMinDistance = DefaultBarkMinDistance; barkMaxDistance = DefaultBarkMaxDistance; }
                else { barkMinDistance = Math.Min(barkMinDistance, MaxBarkDistance); barkMaxDistance = Math.Min(barkMaxDistance, MaxBarkDistance); }
            }
            if (!(barkMaxDistance > barkMinDistance))
            {
                warnings.Add($"BarkMaxDistance = {barkMaxDistance} muss größer als BarkMinDistance ({barkMinDistance}) sein; verwende {DefaultBarkMinDistance}–{DefaultBarkMaxDistance}.");
                barkMinDistance = DefaultBarkMinDistance;
                barkMaxDistance = DefaultBarkMaxDistance;
            }
            return new VoiceSettings
            {
                Enabled = enabled,
                DialogPercent = ClampPercent("DialogVolume", dialogPercent, warnings),
                PlayerPercent = ClampPercent("PlayerVolume", playerPercent, warnings),
                Language = CleanLanguage(language, warnings),
                CacheMegabytes = ClampCache(cacheMegabytes, warnings),
                Diagnostics = diagnostics,
                BarkPercent = ClampPercent("BarkVolume", barkPercent, warnings),
                BarkMinDistance = barkMinDistance,
                BarkMaxDistance = barkMaxDistance,
            };
        }

        /// <summary>Neuer Schnappschuss: Datei-Einstellungen (this) mit den gesetzten Menüwerten darüber; gleiche Grenzen wie <see cref="Create"/>.</summary>
        public VoiceSettings WithOverrides(MenuValues values, List<string> warnings)
        {
            float min = values.BarkMinDistance ?? BarkMinDistance, max = values.BarkMaxDistance ?? BarkMaxDistance;
            if (!float.IsNaN(min) && !float.IsNaN(max) && !float.IsInfinity(min) && !float.IsInfinity(max) && min >= 0f && !(max > min))
            {
                // Menü: Min und Max überlappen. Das Min bleibt, wie eingestellt; das Max rückt knapp darüber (nicht auf die Standardwerte zurück).
                min = Math.Min(min, MaxBarkDistance - 10f);
                max = Math.Min(min + 10f, MaxBarkDistance);
                warnings.Add($"BarkMaxDistance muss größer als BarkMinDistance sein; setze {min}–{max}.");
            }
            return Create(values.Enabled ?? Enabled, values.DialogPercent ?? DialogPercent, values.PlayerPercent ?? PlayerPercent,
                          Language, CacheMegabytes, Diagnostics, warnings, values.BarkPercent ?? BarkPercent,
                          min, max);
        }

        public static SettingsChange Diff(VoiceSettings oldSettings, VoiceSettings newSettings)
        {
            var change = SettingsChange.None;
            if (oldSettings.Enabled != newSettings.Enabled) change |= SettingsChange.Enabled;
            if (oldSettings.DialogPercent != newSettings.DialogPercent || oldSettings.PlayerPercent != newSettings.PlayerPercent
                || oldSettings.BarkPercent != newSettings.BarkPercent) change |= SettingsChange.Volume;
            if (oldSettings.BarkMinDistance != newSettings.BarkMinDistance || oldSettings.BarkMaxDistance != newSettings.BarkMaxDistance)
                change |= SettingsChange.Range;
            return change;
        }

        private static int ClampPercent(string name, int value, List<string> warnings)
        {
            int clamped = Gain.ClampPercent(value);
            if (clamped != value) warnings.Add($"{name} = {value} liegt außerhalb 0–{Gain.MaxPercent}; verwende {clamped}.");
            return clamped;
        }

        private static int ClampCache(int value, List<string> warnings)
        {
            int clamped = value < MinCacheMegabytes ? MinCacheMegabytes : value > MaxCacheMegabytes ? MaxCacheMegabytes : value;
            if (clamped != value) warnings.Add($"CacheMB = {value} liegt außerhalb {MinCacheMegabytes}–{MaxCacheMegabytes}; verwende {clamped}.");
            return clamped;
        }

        private static string CleanLanguage(string? language, List<string> warnings)
        {
            string value = (language ?? "").Trim();
            if (value.Length > 0 && value.Length <= MaxLanguageLength && IsFolderSafe(value)) return value;
            warnings.Add($"AudioLanguage = '{language}' ist kein gültiger Ordnername; verwende '{DefaultLanguage}'.");
            return DefaultLanguage;
        }

        private static bool IsFolderSafe(string value)
        {
            foreach (char c in value)
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
            return true;
        }
    }
}
