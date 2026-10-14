using System.Collections.Generic;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Hält die geladenen Clips innerhalb des Budgets. Verdrängte Clips werden zerstört; das Spiel sieht danach
    /// <c>statement.audio == null</c> und die API ruft beim nächsten Ausführen der Zeile erneut den Connector.
    /// </summary>
    internal sealed class ClipStore
    {
        private readonly ClipBudget _budget;
        private readonly Dictionary<string, AudioClip> _clips = new Dictionary<string, AudioClip>();

        public ClipStore(long maxBytes, int protectedRecent = 8)
        {
            _budget = new ClipBudget(maxBytes, protectedRecent);
        }

        public int Count => _clips.Count;
        public long TotalBytes => _budget.TotalBytes;

        public bool TryGet(string id, out AudioClip clip)
        {
            if (_clips.TryGetValue(id, out var found))
            {
                if (found != null) { _budget.Touch(id); clip = found; return true; }
                _clips.Remove(id);       // vom Spiel zerstört (z. B. Szenenwechsel): vergessen
                _budget.Remove(id);
            }
            clip = null!;
            return false;
        }

        public void Put(string id, AudioClip clip, long bytes)
        {
            _clips[id] = clip;
            foreach (string evictedId in _budget.Add(id, bytes))
            {
                if (_clips.Remove(evictedId, out var old) && old != null) Object.Destroy(old);
            }
        }
    }
}
