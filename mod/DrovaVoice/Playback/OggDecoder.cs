using System;
using System.IO;
using DrovaVoice.Core;
using NVorbis;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// OGG Vorbis -> float-Samples (verschachtelt bei mehreren Kanälen). Wirft nie; Fehler kommen als Text zurück.
    /// Der Dateistrom wird immer geschlossen, auch wenn der Reader beim Öffnen wirft, und er sperrt die Datei
    /// nicht gegen ein Ersetzen durch <c>install</c>.
    /// </summary>
    public static class OggDecoder
    {
        public static bool TryDecode(string path, out float[] samples, out int channels, out int sampleRate, out string? error)
        {
            samples = Array.Empty<float>();
            channels = 0;
            sampleRate = 0;
            error = null;
            FileStream? stream = null;
            VorbisReader? reader = null;
            try
            {
                if (!File.Exists(path)) { error = "Datei fehlt"; return false; }
                stream = OggFile.OpenRead(path);
                reader = new VorbisReader(stream, false);
                channels = reader.Channels;
                sampleRate = reader.SampleRate;
                error = PcmBuffer.Reject(reader.TotalSamples, channels, sampleRate, out int floats);
                if (error != null) return Fail(ref channels, ref sampleRate);
                var buffer = new float[floats];
                int read = 0;
                while (read < buffer.Length)
                {
                    int n = reader.ReadSamples(buffer, read, buffer.Length - read);
                    if (n <= 0) break;
                    read += n;
                }
                read = PcmBuffer.Align(read, channels);
                if (read < 1) { error = "keine Samples lesbar"; return Fail(ref channels, ref sampleRate); }
                if (read < buffer.Length) Array.Resize(ref buffer, read);
                samples = buffer;
                error = null;
                return true;
            }
            catch (Exception e)
            {
                error = e.GetType().Name + ": " + e.Message;
                samples = Array.Empty<float>();
                channels = 0;
                sampleRate = 0;
                return false;
            }
            finally
            {
                try { reader?.Dispose(); } catch (Exception) { }
                try { stream?.Dispose(); } catch (Exception) { }
            }
        }

        private static bool Fail(ref int channels, ref int sampleRate)
        {
            channels = 0;
            sampleRate = 0;
            return false;
        }
    }
}
