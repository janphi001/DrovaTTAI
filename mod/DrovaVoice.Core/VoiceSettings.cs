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
        public const float DefaultBarkMinDistance = 3f;
        public const float DefaultBarkMaxDistance = 30f;
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
            if (barkMinDistance < 0f) barkMinDistance = 0f;
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
