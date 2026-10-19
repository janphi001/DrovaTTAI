using System;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Dekodiertes PCM ohne Unity-Typen. Ein Hintergrundthread erzeugt es, der Hauptthread baut daraus den AudioClip.
    /// </summary>
    public sealed class DecodedClip
    {
        public DecodedClip(float[] samples, int channels, int sampleRate, long elapsedMilliseconds)
        {
            if (samples == null) throw new ArgumentNullException(nameof(samples));
            if (channels < 1) throw new ArgumentOutOfRangeException(nameof(channels));
            if (sampleRate < 1) throw new ArgumentOutOfRangeException(nameof(sampleRate));
            if (elapsedMilliseconds < 0) throw new ArgumentOutOfRangeException(nameof(elapsedMilliseconds));
            Samples = samples;
            Channels = channels;
            SampleRate = sampleRate;
            ElapsedMilliseconds = elapsedMilliseconds;
        }

        public float[] Samples { get; }
        public int Channels { get; }
        public int SampleRate { get; }
        public long ElapsedMilliseconds { get; }
        public long Bytes => (long)Samples.Length * sizeof(float);
    }
}
