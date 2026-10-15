using System;
using System.Diagnostics;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Datei -> Samples -> Gain -> AudioClip. Läuft synchron auf dem Hauptthread. Eine einmalig langsame Zeile (JIT, kalter
    /// Dateicache) bleibt hörbar: der fertige Clip wird behalten, die Dauer nur gemeldet.
    /// </summary>
    internal sealed class ClipLoader
    {
        public const int SlowMilliseconds = 500;
        public const string ClipNamePrefix = "DrovaVoice/";
        private readonly string _audioRoot;

        public ClipLoader(string audioRoot) { _audioRoot = audioRoot; }

        /// <summary>null = Zeile bleibt stumm (<paramref name="error"/> sagt warum). Wirft nie.</summary>
        public AudioClip? Load(IndexEntry entry, int percent, out long bytes, out long elapsedMs, out string? error)
        {
            bytes = 0;
            elapsedMs = 0;
            AudioClip? clip = null;
            try
            {
                string? path = AudioIndex.ResolvePath(_audioRoot, entry.File);
                if (path == null) { error = "unsicherer Pfad"; return null; }
                var watch = Stopwatch.StartNew();
                if (!OggDecoder.TryDecode(path, out float[] samples, out int channels, out int sampleRate, out error)) return null;
                Gain.Apply(samples, percent);
                int frames = samples.Length / channels;
                clip = AudioClip.Create(ClipNamePrefix + entry.File, frames, channels, sampleRate, false);
                if (clip == null || !clip.SetData(samples, 0))
                {
                    if (clip != null) UnityEngine.Object.Destroy(clip);
                    error = "AudioClip konnte nicht erzeugt werden";
                    return null;
                }
                watch.Stop();
                elapsedMs = watch.ElapsedMilliseconds;
                bytes = (long)samples.Length * sizeof(float);
                error = null;
                return clip;
            }
            catch (Exception e)
            {
                if (clip != null) { try { UnityEngine.Object.Destroy(clip); } catch (Exception) { } }
                error = e.GetType().Name + ": " + e.Message;
                return null;
            }
        }
    }
}
