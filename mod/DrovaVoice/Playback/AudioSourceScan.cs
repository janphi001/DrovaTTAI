using System;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Eine <c>FindObjectsOfType</c>-Suche für <see cref="BarkDistance"/> und <see cref="StaleAudioProbe"/>.
    /// Höchstens alle <see cref="IntervalSeconds"/>, unabhängig von der Bildrate. Schlägt die Suche fehl,
    /// bleibt die letzte Liste stehen und der nächste Frame versucht es erneut.
    /// </summary>
    internal sealed class AudioSourceScan
    {
        public const double IntervalSeconds = 0.25;

        private readonly ScanScheduler _scheduler = new ScanScheduler(IntervalSeconds);
        private AudioSource[] _sources = Array.Empty<AudioSource>();
        private int _generation;

        public int Generation => _generation;
        public AudioSource[] Sources => _sources;

        /// <summary>True, wenn diese Suche eine neue Liste veröffentlicht hat.</summary>
        public bool Tick(double nowSeconds)
        {
            if (!_scheduler.IsDue(nowSeconds)) return false;
            var found = UnityEngine.Object.FindObjectsOfType<AudioSource>(true) ?? Array.Empty<AudioSource>();
            _scheduler.MarkRan(nowSeconds);
            _sources = found;
            _generation++;
            return true;
        }
    }
}
