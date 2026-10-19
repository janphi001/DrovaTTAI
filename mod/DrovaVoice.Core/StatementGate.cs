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

        /// <summary>
        /// Nur Clips dieser Mod werden geleert (Barks und Poolzeilen teilen die Aussage zwischen Figuren; der Connector
        /// holt den passenden Clip danach aus dem Cache). Fremde Clips, etwa von einer anderen Sprachmod, bleiben.
        /// </summary>
        public static bool ClearAttachedClip(string? clipName, string modPrefix) =>
            clipName != null && clipName.StartsWith(modPrefix, System.StringComparison.Ordinal);
    }
}
