using System;
using System.IO;
using NVorbis;

namespace DrovaVoice.Playback
{
    /// <summary>OGG Vorbis -> float-Samples (verschachtelt bei mehreren Kanälen). Wirft nie; Fehler kommen als Text zurück.</summary>
    public static class OggDecoder
    {
        private const long MaxSamples = 48000L * 60 * 2; // 60 s Stereo bei 48 kHz: Schutz gegen absurd große Dateien

        public static bool TryDecode(string path, out float[] samples, out int channels, out int sampleRate, out string? error)
        {
            samples = Array.Empty<float>();
            channels = 0;
            sampleRate = 0;
            error = null;
            try
            {
                if (!File.Exists(path)) { error = "Datei fehlt"; return false; }
                using var reader = new VorbisReader(path);
                channels = reader.Channels;
                sampleRate = reader.SampleRate;
                long total = reader.TotalSamples * channels;
                if (channels < 1 || sampleRate < 1 || total < 1) { error = "leere oder ungültige Datei"; return false; }
                if (total > MaxSamples) { error = $"Datei zu lang ({total} Samples)"; return false; }
                var buffer = new float[total];
                int read = 0;
                while (read < buffer.Length)
                {
                    int n = reader.ReadSamples(buffer, read, buffer.Length - read);
                    if (n <= 0) break;
                    read += n;
                }
                if (read < 1) { error = "keine Samples lesbar"; return false; }
                if (read < buffer.Length) Array.Resize(ref buffer, read);
                samples = buffer;
                return true;
            }
            catch (Exception e)
            {
                error = e.GetType().Name + ": " + e.Message;
                samples = Array.Empty<float>();
                return false;
            }
        }
    }
}
