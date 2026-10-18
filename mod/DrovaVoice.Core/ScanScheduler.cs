using System;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Zeitbasierte Drossel für einen gemeinsamen Lauf, zum Beispiel eine AudioSource-Suche.
    /// <see cref="IsDue"/> ändert nichts. <see cref="MarkRan"/> merkt sich den Lauf und öffnet das nächste Intervall.
    /// Springt die Uhr zurück, ist der nächste Lauf sofort fällig, damit die Suche nicht stehen bleibt.
    /// </summary>
    public sealed class ScanScheduler
    {
        private readonly double _intervalSeconds;
        private double? _last;

        public ScanScheduler(double intervalSeconds)
        {
            if (intervalSeconds <= 0d || double.IsNaN(intervalSeconds) || double.IsInfinity(intervalSeconds))
                throw new ArgumentOutOfRangeException(nameof(intervalSeconds));
            _intervalSeconds = intervalSeconds;
        }

        public double IntervalSeconds => _intervalSeconds;

        public bool IsDue(double nowSeconds)
        {
            if (_last is not double last) return true;
            double elapsed = nowSeconds - last;
            return elapsed < 0d || elapsed >= _intervalSeconds;
        }

        public void MarkRan(double nowSeconds) => _last = nowSeconds;
    }
}
