namespace DrovaVoice.Core
{
    /// <summary>
    /// Der API-Prefix auf dem Aussageknoten ruft den Connector nur auf, solange kein Clip hängt.
    /// Ein Clip der vorherigen Figur im selben Frame würde sonst wiederverwendet.
    /// Die Priorität liegt über Harmony <c>Priority.First</c> (800), damit dieses Leeren davor läuft.
    /// </summary>
    public static class StatementGate
    {
        public const int BeforeApiPrefix = 801;

        public static bool ClearAttachedClip(bool hasClip) => hasClip;
    }
}
