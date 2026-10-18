using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>Entscheidet, ob ein Schlüssel (z. B. eine Zeilen-ID) schon geloggt wurde. Ab der Obergrenze werden keine neuen Schlüssel mehr gemeldet.</summary>
    public sealed class OnceLog
    {
        private readonly HashSet<string> _seen = new HashSet<string>(StringComparer.Ordinal);
        private readonly int _cap;

        public OnceLog(int cap = 10000) { _cap = cap; }

        public bool ShouldLog(string key)
        {
            if (_seen.Contains(key)) return false;
            if (_seen.Count >= _cap) return false;
            _seen.Add(key);
            return true;
        }

        /// <summary>Nach einem Index-Reload, damit ein erneuter Ladefehler derselben Zeile wieder im Log steht.</summary>
        public void Clear() => _seen.Clear();
    }
}
