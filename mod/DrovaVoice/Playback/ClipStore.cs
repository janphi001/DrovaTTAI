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
        private readonly List<(AudioClip Clip, float DestroyAt)> _retired = new List<(AudioClip, float)>();

        /// <summary>Zuschlag nach Clipende, bevor ein ausgemusterter Clip zerstört wird. Deckt auch eine kurze Pause (Esc) ab.</summary>
        public const float RetireGraceSeconds = 30f;

        public ClipStore(long maxBytes, int protectedRecent = 8)
        {
            _budget = new ClipBudget(maxBytes, protectedRecent);
        }

        public int Count => _clips.Count;
        public long TotalBytes => _budget.TotalBytes;

        public bool TryGet(string id, out AudioClip clip)
        {
            SweepRetired();
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

        /// <summary>
        /// Vergisst alle gehaltenen Clips nach einem Index-Reload, damit ersetzte Dateien neu geladen werden.
        /// Zerstört werden sie erst, wenn sie sicher ausgespielt sind: eine laufende Zeile bricht nicht ab.
        /// </summary>
        public void Clear()
        {
            float now = Time.unscaledTime;
            foreach (var pair in _clips)
            {
                if (pair.Value != null) _retired.Add((pair.Value, now + pair.Value.length + RetireGraceSeconds));
                _budget.Remove(pair.Key);
            }
            _clips.Clear();
        }

        private void SweepRetired()
        {
            if (_retired.Count == 0) return;
            float now = Time.unscaledTime;
            for (int i = _retired.Count - 1; i >= 0; i--)
            {
                if (_retired[i].DestroyAt > now) continue;
                if (_retired[i].Clip != null) Object.Destroy(_retired[i].Clip);
                _retired.RemoveAt(i);
            }
        }
    }
}
