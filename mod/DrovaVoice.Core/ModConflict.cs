using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>
    /// DrovaTTS (Assembly <c>DrovaTTS</c>, Melon-Name „Drova TTS“) ersetzt denselben Dialog-Connector.
    /// Sind beide Mods geladen, gewinnt der letzte Aufruf und die andere bleibt stumm.
    /// </summary>
    public static class ModConflict
    {
        public const string DrovaTtsWarning =
            "DrovaTTS ist geladen (Mod-Liste „Drova TTS“ oder Assembly DrovaTTS). Beide Mods ersetzen denselben Dialog-Connector; eine bleibt stumm. DrovaVoice und DrovaTTS nicht zusammen verwenden.";

        public static bool DrovaTtsLoaded(IEnumerable<string?> melonNames, IEnumerable<string?> assemblyNames) =>
            ContainsDrovaTts(melonNames) || ContainsDrovaTts(assemblyNames);

        public static bool IsDrovaTtsName(string? name)
        {
            if (string.IsNullOrEmpty(name)) return false;
            int comma = name.IndexOf(',');
            if (comma >= 0) name = name.Substring(0, comma);
            return Compact(name) == "drovatts";
        }

        private static bool ContainsDrovaTts(IEnumerable<string?> names)
        {
            foreach (string? name in names)
                if (IsDrovaTtsName(name)) return true;
            return false;
        }

        private static string Compact(string name)
        {
            var buffer = new char[name.Length];
            int count = 0;
            foreach (char c in name)
            {
                if (c == ' ' || c == '\t' || c == '_' || c == '-') continue;
                buffer[count++] = char.ToLowerInvariant(c);
            }
            return new string(buffer, 0, count);
        }
    }
}
