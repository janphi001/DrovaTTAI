using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Entscheidet, wann der Clip einer stillen AudioSource abgenommen wird.
    /// Die Frist ist eine Zeitspanne, unabhängig von der Bildrate. Eine pausierte Quelle
    /// (Wiedergabezeit &gt; 0 und sie spielt nicht) behält den Clip; die Pause zählt nicht als Leerlauf.
    /// </summary>
    public sealed class IdleClipPolicy
    {
        /// <summary>Abstand der Prüfungen. Ersetzt die früheren 15 Frames (bei 60 Bildern/s eine Viertelsekunde).</summary>
        public const float ScanIntervalSeconds = 0.25f;

        /// <summary>So lange muss die Quelle am Stück stillstehen (Zeit 0, spielt nicht), bevor der Clip abgenommen wird. Entspricht den früheren zwei Scans, etwa eine halbe Sekunde.</summary>
        public const float IdleSeconds = 0.5f;

        private readonly Dictionary<int, float> _idleSince = new Dictionary<int, float>();

        /// <summary>
        /// True, wenn der Clip dieser Quelle jetzt abgenommen werden soll.
        /// <paramref name="playbackTimeSeconds"/> ist <c>AudioSource.time</c>, <paramref name="nowSeconds"/> eine laufende Uhr (auch bei Pause des Spiels).
        /// </summary>
        public bool ShouldStrip(int sourceId, bool isPlaying, float playbackTimeSeconds, float nowSeconds)
        {
            if (isPlaying || playbackTimeSeconds > 0f)
            {
                _idleSince.Remove(sourceId);
                return false;
            }
            if (!_idleSince.TryGetValue(sourceId, out float since))
            {
                _idleSince[sourceId] = nowSeconds;
                return false;
            }
            if (nowSeconds - since < IdleSeconds) return false;
            _idleSince.Remove(sourceId);
            return true;
        }

        /// <summary>Quellen, die keinen Clip der Mod mehr halten, vergessen. Sonst könnte eine wiedervergebene Instanz-ID zu früh abgenommen werden.</summary>
        public void ForgetUnseen(IReadOnlySet<int> seen)
        {
            if (_idleSince.Count == 0) return;
            List<int>? stale = null;
            foreach (int id in _idleSince.Keys)
            {
                if (seen.Contains(id)) continue;
                stale ??= new List<int>();
                stale.Add(id);
            }
            if (stale == null) return;
            foreach (int id in stale) _idleSince.Remove(id);
        }
    }
}
