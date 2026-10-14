using System.Diagnostics;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>Datei -> Samples -> Gain -> AudioClip. Läuft synchron auf dem Hauptthread; über 500 ms bleibt die Zeile stumm.</summary>
    internal sealed class ClipLoader
    {
        public const int MaxDecodeMilliseconds = 500;
        private readonly string _audioRoot;

        public ClipLoader(string audioRoot) { _audioRoot = audioRoot; }

        public AudioClip? Load(string id, IndexEntry entry, int percent, out long bytes, out string? error)
        {
            bytes = 0;
            string? path = AudioIndex.ResolvePath(_audioRoot, entry.File);
            if (path == null) { error = "unsicherer Pfad"; return null; }
            var watch = Stopwatch.StartNew();
            if (!OggDecoder.TryDecode(path, out float[] samples, out int channels, out int sampleRate, out error)) return null;
            Gain.Apply(samples, percent);
            int frames = samples.Length / channels;
            var clip = AudioClip.Create("DrovaVoice/" + entry.File, frames, channels, sampleRate, false);
            if (clip == null || !clip.SetData(samples, 0)) { error = "AudioClip konnte nicht erzeugt werden"; return null; }
            watch.Stop();
            if (watch.ElapsedMilliseconds > MaxDecodeMilliseconds)
            {
                Object.Destroy(clip);
                error = $"Dekodieren dauerte {watch.ElapsedMilliseconds} ms (Grenze {MaxDecodeMilliseconds} ms)";
                return null;
            }
            bytes = (long)samples.Length * sizeof(float);
            error = null;
            return clip;
        }
    }
}
