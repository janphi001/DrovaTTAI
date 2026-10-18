using System;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Führt einen Harmony-Prefix oder einen Connector-Aufruf aus. Eine Ausnahme bleibt im Patch:
    /// sie wird gemeldet, und eine Ausnahme in der Meldung selbst darf das Spiel nicht erreichen.
    /// </summary>
    public static class PatchGuard
    {
        public static void Run(Action body, Action<Exception> onError)
        {
            try
            {
                body();
            }
            catch (Exception e)
            {
                try { onError(e); }
                catch (Exception) { }
            }
        }
    }
}
