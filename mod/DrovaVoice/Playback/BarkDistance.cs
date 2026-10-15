using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Drova_Modding_API.Access;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Dämpft Barks laufend nach dem Abstand zum Spieler: nah laut, beim Entfernen leiser, beim Annähern wieder lauter.
    /// Das Spiel spielt unsere Clips auf eigenen AudioSources; sobald ein Bark-Clip (Clipname <c>DrovaVoice/bark/…</c>) spielt,
    /// regelt diese Klasse in jedem Frame <c>AudioSource.volume</c> nach <see cref="BarkAttenuation"/>. Am Ende (oder wenn die
    /// Quelle einen anderen Clip bekommt) wird die ursprüngliche Lautstärke wiederhergestellt, weil dieselbe Quelle später
    /// normale Dialoge spielt.
    /// </summary>
    internal sealed class BarkDistance
    {
        public const string BarkClipPrefix = ClipLoader.ClipNamePrefix + "bark/";
        private const int ScanFramesAfterBark = 90;   // so lange nach einem Bark wird jeden Frame nach der spielenden Quelle gesucht

        private sealed class Tracked
        {
            public AudioSource Source = null!;
            public float OriginalVolume;
        }

        private readonly float _min, _max;
        private readonly MelonLogger.Instance _log;
        private readonly bool _verbose;
        private readonly List<Tracked> _tracked = new List<Tracked>();
        private readonly HashSet<int> _ids = new HashSet<int>();
        private int _scanFrames;
        private bool _warnedNoPlayer;

        public BarkDistance(float min, float max, MelonLogger.Instance log, bool verbose)
        {
            _min = min; _max = max; _log = log; _verbose = verbose;
        }

        /// <summary>Ein Bark-Clip wurde gerade an eine Aussage gehängt; ab jetzt wird nach der spielenden Quelle gesucht.</summary>
        public void Expect() { _scanFrames = ScanFramesAfterBark; }

        public void Update()
        {
            try
            {
                if (_scanFrames > 0) { _scanFrames--; FindPlayingBarks(); }
                if (_tracked.Count > 0) Apply();
            }
            catch (Exception e) { _log.Warning($"Bark-Entfernung: {e.GetType().Name}: {e.Message}"); }
        }

        private void FindPlayingBarks()
        {
            foreach (var source in UnityEngine.Object.FindObjectsOfType<AudioSource>(true))
            {
                if (source == null || !source.isPlaying) continue;
                var clip = source.clip;
                if (clip == null || clip.name == null || !clip.name.StartsWith(BarkClipPrefix, StringComparison.Ordinal)) continue;
                if (!_ids.Add(source.GetInstanceID())) continue;
                _tracked.Add(new Tracked { Source = source, OriginalVolume = source.volume });
                if (_verbose) _log.Msg($"[Bark] Entfernungsregelung für {clip.name} (Lautstärke vorher {source.volume:0.00})");
            }
        }

        private void Apply()
        {
            bool havePlayer = TryPlayerPosition(out Vector2 player);
            for (int i = _tracked.Count - 1; i >= 0; i--)
            {
                var t = _tracked[i];
                var source = t.Source;
                bool done = source == null || !source.isPlaying || source.clip == null
                            || source.clip.name == null || !source.clip.name.StartsWith(BarkClipPrefix, StringComparison.Ordinal);
                if (done)
                {
                    if (source != null) source.volume = t.OriginalVolume;
                    if (source != null) _ids.Remove(source.GetInstanceID());
                    _tracked.RemoveAt(i);
                    continue;
                }
                if (!havePlayer) continue;   // Spieler unbekannt: Lautstärke unverändert lassen
                var pos = source.transform.position;
                float distance = Vector2.Distance(player, new Vector2(pos.x, pos.y));
                source.volume = t.OriginalVolume * BarkAttenuation.Gain(distance, _min, _max);
            }
            if (_tracked.Count == 0) _ids.Clear();
        }

        private bool TryPlayerPosition(out Vector2 position)
        {
            position = default;
            try
            {
                if (!PlayerAccess.TryGetPlayer(out var actor) || actor == null) { WarnNoPlayer(); return false; }
                var p = actor.transform.position;
                position = new Vector2(p.x, p.y);
                return true;
            }
            catch (Exception) { WarnNoPlayer(); return false; }
        }

        private void WarnNoPlayer()
        {
            if (_warnedNoPlayer) return;
            _warnedNoPlayer = true;
            _log.Warning("Bark-Entfernung: Spielerposition nicht lesbar; Barks bleiben unverändert laut.");
        }
    }
}
