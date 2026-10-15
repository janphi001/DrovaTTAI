using System;

namespace DrovaVoice.Core
{
    /// <summary>Werte aus dem Optionsmenü; null = nicht gesetzt (Wert der Datei-Einstellungen bleibt).</summary>
    public sealed record MenuValues(bool? Enabled = null, int? DialogPercent = null, int? PlayerPercent = null,
                                    int? BarkPercent = null, float? BarkMinDistance = null, float? BarkMaxDistance = null);

    /// <summary>Schlüssel im Konfigurationsspeicher des Spiels (Optionsmenü).</summary>
    public static class MenuKeys
    {
        public const string Enabled = "DrovaVoice_Enabled";
        public const string DialogVolume = "DrovaVoice_DialogVolume";
        public const string PlayerVolume = "DrovaVoice_PlayerVolume";
        public const string BarkVolume = "DrovaVoice_BarkVolume";
        public const string BarkMinDistance = "DrovaVoice_BarkMinDistance";
        public const string BarkMaxDistance = "DrovaVoice_BarkMaxDistance";
    }

    [Flags]
    public enum SettingsChange { None = 0, Enabled = 1, Volume = 2, Range = 4 }
}
