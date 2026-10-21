using System;
using System.Diagnostics;
using MelonLoader;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Messung für Bildrateneinbrüche (nur mit BarkProbe): je Sekunde eine Zeile mit Bildrate, schlechtestem Bild,
    /// Zeit der Mod je Abschnitt, Anzahl Audioquellen der Suche und laufenden Barks sowie verwaltetem Speicher.
    /// </summary>
    internal sealed class FrameProbe
    {
        public enum Part { Scan, Sonde, Bark, Stimme, Tempo, Connector }
        private static readonly int PartCount = Enum.GetValues(typeof(Part)).Length;

        public static FrameProbe? Active;

        private readonly MelonLogger.Instance _log;
        private readonly double[] _sum = new double[PartCount];
        private readonly double[] _max = new double[PartCount];
        private readonly double[] _frame = new double[PartCount];
        private double _windowStart = -1;
        private int _frames;
        private double _worstFrame;
        private double _modWorstFrame;
        private int _barkFrames;
        private int _gen0, _gen2;
        private long _allocated;

        public FrameProbe(MelonLogger.Instance log) { _log = log; }

        public long Start() => Stopwatch.GetTimestamp();

        public void Stop(Part part, long started) =>
            _frame[(int)part] += (Stopwatch.GetTimestamp() - started) * 1000.0 / Stopwatch.Frequency;

        /// <summary>Einmal je Bild am Anfang von OnUpdate: schließt das vorige Bild ab.</summary>
        public void EndFrame(double now, float deltaSeconds, int sources, bool barkBusy)
        {
            if (_windowStart < 0) { Reset(now); Array.Clear(_frame); return; }
            double modFrame = 0;
            for (int i = 0; i < PartCount; i++)
            {
                _sum[i] += _frame[i];
                if (_frame[i] > _max[i]) _max[i] = _frame[i];
                modFrame += _frame[i];
                _frame[i] = 0;
            }
            _frames++;
            double ms = deltaSeconds * 1000.0;
            if (ms > _worstFrame) _worstFrame = ms;
            if (modFrame > _modWorstFrame) _modWorstFrame = modFrame;
            if (barkBusy) _barkFrames++;
            if (now - _windowStart < 1.0) return;
            double span = now - _windowStart;
            int gen0 = GC.CollectionCount(0) - _gen0, gen2 = GC.CollectionCount(2) - _gen2;
            long alloc = GC.GetTotalAllocatedBytes() - _allocated;
            var parts = new System.Text.StringBuilder();
            for (int i = 0; i < PartCount; i++)
                parts.Append($" {(Part)i}={_sum[i]:0.0}/{_max[i]:0.0}");
            _log.Msg($"[Bilder] {_frames / span:0} fps, schlechtestes {_worstFrame:0.0} ms, Mod je Bild max {_modWorstFrame:0.0} ms, Summe/Max ms:{parts}, Quellen={sources}, Barkbilder={_barkFrames}, GC0={gen0} GC2={gen2}, alloc={alloc / 1024} KB");
            Reset(now);
        }

        private void Reset(double now)
        {
            _windowStart = now;
            _frames = 0;
            _worstFrame = 0;
            _modWorstFrame = 0;
            _barkFrames = 0;
            Array.Clear(_sum);
            Array.Clear(_max);
            _gen0 = GC.CollectionCount(0);
            _gen2 = GC.CollectionCount(2);
            _allocated = GC.GetTotalAllocatedBytes();
        }
    }
}
