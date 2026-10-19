using System;
using System.Diagnostics;
using DrovaVoice.Core;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Datei -> Samples -> Gain, und getrennt davon Samples -> AudioClip.
    /// <see cref="Decode"/> ruft kein Unity auf und darf auf einem Hintergrundthread laufen.
    /// <see cref="CreateClip"/> bleibt auf dem Hauptthread. Eine einmalig langsame Zeile bleibt hörbar:
    /// der fertige Clip wird behalten, die Dauer nur gemeldet.
    /// </summary>
    internal sealed class ClipLoader
    {
        public const int SlowMilliseconds = 500;
        public static readonly TimeSpan DecodeWait = TimeSpan.FromSeconds(5);
        public const string ClipNamePrefix = "DrovaVoice/";
        private readonly string _audioRoot;

        public ClipLoader(string audioRoot) { _audioRoot = audioRoot; }

        /// <summary>Kein Unity. Wirft nie. <paramref name="elapsedMilliseconds"/> ist nur die Dekodierung, nicht das Erzeugen des Clips.</summary>
        public PcmDecode Decode(IndexEntry entry, int percent)
        {
            var watch = Stopwatch.StartNew();
            try
            {
                string? path = AudioIndex.ResolvePath(_audioRoot, entry.File);
                if (path == null) return PcmDecode.Failed("unsicherer Pfad");
                if (!OggDecoder.TryDecode(path, out float[] samples, out int channels, out int sampleRate, out string? error))
                    return PcmDecode.Failed(error ?? "Dekodieren fehlgeschlagen");
                Gain.Apply(samples, percent);
                watch.Stop();
                return new PcmDecode(samples, channels, sampleRate, watch.ElapsedMilliseconds, null);
            }
            catch (Exception e)
            {
                return PcmDecode.Failed(e.GetType().Name + ": " + e.Message);
            }
        }

        /// <summary>Nur Hauptthread. null = Zeile bleibt stumm (<paramref name="error"/> sagt warum). Wirft nie.</summary>
        public AudioClip? CreateClip(IndexEntry entry, DecodedClip decoded, out string? error)
        {
            AudioClip? clip = null;
            try
            {
                int frames = decoded.Samples.Length / decoded.Channels;
                clip = AudioClip.Create(ClipNamePrefix + entry.File, frames, decoded.Channels, decoded.SampleRate, false);
                if (clip == null || !clip.SetData(decoded.Samples, 0))
                {
                    if (clip != null) UnityEngine.Object.Destroy(clip);
                    error = "AudioClip konnte nicht erzeugt werden";
                    return null;
                }
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

    /// <summary>PCM aus <see cref="ClipLoader.Decode"/>. <see cref="Error"/> gesetzt heißt: keine Samples.</summary>
    internal readonly struct PcmDecode
    {
        public PcmDecode(float[]? samples, int channels, int sampleRate, long elapsedMilliseconds, string? error)
        {
            Samples = samples;
            Channels = channels;
            SampleRate = sampleRate;
            ElapsedMilliseconds = elapsedMilliseconds;
            Error = error;
        }

        public float[]? Samples { get; }
        public int Channels { get; }
        public int SampleRate { get; }
        public long ElapsedMilliseconds { get; }
        public string? Error { get; }

        public static PcmDecode Failed(string error) => new PcmDecode(null, 0, 0, 0, error);
    }
}
