using System;
using System.Collections.Generic;
using System.Text;
using DrovaVoice.Core;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Diagnose für „alte Dialoge spielen beim Herumlaufen ab“ (nur mit Diagnostics): Das Spiel spielt unsere Clips selbst, die Mod
    /// sieht davon nichts. Die Sonde sucht darum ein paar Mal pro Sekunde alle AudioSources, die einen Clip der Mod halten
    /// (Clipname beginnt mit <see cref="ClipLoader.ClipNamePrefix"/>), und meldet jede Zustandsänderung: beginnt zu spielen,
    /// hört auf, hält den Clip im Leerlauf. Ein Leerlauf-Halter mit playOnAwake oder ein Start ohne Gespräch ist der Beleg.
    /// </summary>
    internal sealed class StaleAudioProbe
    {
        private readonly MelonLogger.Instance _log;
        private readonly Dictionary<int, string> _lastState = new Dictionary<int, string>();
        private readonly bool _verbose;
        private readonly IdleClipPolicy _idle = new IdleClipPolicy();
        private float _nextScan = -1f;

        public StaleAudioProbe(MelonLogger.Instance log, bool verbose) { _log = log; _verbose = verbose; }

        public void Update()
        {
            float now = Time.unscaledTime;
            if (_nextScan < 0f) { _nextScan = now + IdleClipPolicy.ScanIntervalSeconds; return; }
            if (now < _nextScan) return;
            _nextScan = now + IdleClipPolicy.ScanIntervalSeconds;
            try { Scan(now); }
            catch (Exception e) { _log.Warning($"Audio-Sonde: {e.GetType().Name}: {e.Message}"); }
        }

        private void Scan(float now)
        {
            var sources = UnityEngine.Object.FindObjectsOfType<AudioSource>(true);
            var seen = new HashSet<int>();
            foreach (var source in sources)
            {
                if (source == null) continue;
                var clip = source.clip;
                if (clip == null) continue;
                string name = clip.name ?? "";
                if (!name.StartsWith(ClipLoader.ClipNamePrefix, StringComparison.Ordinal)) continue;
                int id = source.GetInstanceID();
                seen.Add(id);
                if (CleanIdle(source, id, now)) continue;
                if (!_verbose) continue;
                string state = source.isPlaying ? "spielt" : "haelt";
                string key = state + "|" + name;
                if (_lastState.TryGetValue(id, out var previous) && previous == key) continue;
                _lastState[id] = key;
                _log.Msg($"[Sonde] {state}: {name} auf {PathOf(source.transform)} (playOnAwake={source.playOnAwake}, loop={source.loop}, zeit={source.time:0.00}/{clip.length:0.00} s, volume={source.volume:0.00}, aktiv={source.gameObject.activeInHierarchy})");
            }
            _idle.ForgetUnseen(seen);
            if (_verbose && _lastState.Count > seen.Count)
            {
                var gone = new List<int>();
                foreach (int id in _lastState.Keys) if (!seen.Contains(id)) gone.Add(id);
                foreach (int id in gone)
                {
                    _log.Msg($"[Sonde] Quelle {id} hält den Clip nicht mehr ({_lastState[id]})");
                    _lastState.Remove(id);
                }
            }
        }

        /// <summary>
        /// Das Spiel lässt den Clip nach dem Abspielen an der AudioSource (playOnAwake=True) stehen; wird der NPC später neu
        /// aktiviert, spielt die Quelle ihn erneut ab. <see cref="IdleClipPolicy"/> nimmt ihn nach einer halben Sekunde Leerlauf ab.
        /// Eine pausierte Quelle (time &gt; 0) behält den Clip.
        /// </summary>
        private bool CleanIdle(AudioSource source, int id, float now)
        {
            if (!_idle.ShouldStrip(id, source.isPlaying, source.time, now)) return false;
            if (_verbose) _log.Msg($"[Sonde] Clip abgenommen: {source.clip.name} auf {PathOf(source.transform)}");
            source.clip = null;
            _lastState.Remove(id);
            return true;
        }

        private static string PathOf(Transform? t)
        {
            var sb = new StringBuilder();
            for (int depth = 0; t != null && depth < 5; depth++, t = t.parent)
            {
                if (sb.Length > 0) sb.Insert(0, "/");
                sb.Insert(0, t.name);
            }
            return sb.ToString();
        }
    }
}
