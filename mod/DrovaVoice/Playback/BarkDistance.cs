using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Drova_Modding_API.Access;
using Il2CppNodeCanvas.DialogueTrees;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Zwei Aufgaben für Barks und Poolzeilen (generische Figuren), deren Aussage für alle Figuren dieselbe ist:
    /// 1. <b>Aussage freigeben:</b> Hängt der Connector einen Clip an <c>statement.audio</c>, bleibt er dort stehen; bei jeder
    ///    Wiederholung ruft die API den Connector nicht mehr auf, und eine andere Figur spielte die Stimme der ersten (auch mit
    ///    falschem Geschlecht). Sobald der Clip abspielt (oder nach <see cref="TimeoutFrames"/> Frames), wird <c>statement.audio</c>
    ///    wieder auf null gesetzt, damit der Connector bei der nächsten Ausführung neu entscheidet.
    /// 2. <b>Entfernung:</b> Spielt ein Bark-Clip (Clipname <c>DrovaVoice/bark/…</c>), regelt die Klasse in jedem Frame
    ///    <c>AudioSource.volume</c> nach <see cref="BarkAttenuation"/> (nah laut, weiter weg leiser, wieder lauter beim Annähern).
    ///    Am Ende wird die ursprüngliche Lautstärke wiederhergestellt, weil dieselbe Quelle später normale Dialoge spielt.
    ///    Ist die Spielerposition nicht lesbar, wird nichts neu geregelt: Ein laufender Bark behält den zuletzt gesetzten Wert.
    /// </summary>
    internal sealed class BarkDistance
    {
        public const string BarkClipPrefix = ClipLoader.ClipNamePrefix + "bark/";
        private const int TimeoutFrames = 90;

        private sealed class Tracked { public AudioSource Source = null!; public float OriginalVolume; }
        private sealed class Pending { public DS_Statement Statement = null!; public AudioClip Clip = null!; public int Frames; }

        private readonly float _min, _max;
        private readonly MelonLogger.Instance _log;
        private readonly bool _verbose;
        private readonly List<Tracked> _tracked = new List<Tracked>();
        private readonly HashSet<int> _ids = new HashSet<int>();
        private readonly List<Pending> _pending = new List<Pending>();
        private bool _warnedNoPlayer;

        public BarkDistance(float min, float max, MelonLogger.Instance log, bool verbose)
        {
            _min = min; _max = max; _log = log; _verbose = verbose;
        }

        /// <summary>Der Connector hat <paramref name="clip"/> an die Aussage gehängt; sie wird freigegeben, sobald er abspielt.</summary>
        public void Watch(DS_Statement statement, AudioClip clip) => _pending.Add(new Pending { Statement = statement, Clip = clip });

        public void Update()
        {
            try
            {
                if (_pending.Count > 0) ResolvePending();
                if (_tracked.Count > 0) Apply();
            }
            catch (Exception e) { _log.Warning($"Bark-Entfernung: {e.GetType().Name}: {e.Message}"); }
        }

        private void ResolvePending()
        {
            var playing = new List<AudioSource>();
            foreach (var source in UnityEngine.Object.FindObjectsOfType<AudioSource>(true))
            {
                if (source == null || !source.isPlaying || source.clip == null) continue;
                playing.Add(source);
                var clip = source.clip;
                if (clip.name == null || !clip.name.StartsWith(BarkClipPrefix, StringComparison.Ordinal)) continue;
                if (!_ids.Add(source.GetInstanceID())) continue;
                _tracked.Add(new Tracked { Source = source, OriginalVolume = source.volume });
                if (_verbose) _log.Msg($"[Bark] Entfernungsregelung für {clip.name} (Lautstärke vorher {source.volume:0.00})");
            }
            for (int i = _pending.Count - 1; i >= 0; i--)
            {
                var p = _pending[i];
                bool started = false;
                foreach (var s in playing) if (s.clip == p.Clip) { started = true; break; }
                if (!started && ++p.Frames < TimeoutFrames) continue;
                Release(p, started);
                _pending.RemoveAt(i);
            }
        }

        private void Release(Pending p, bool started)
        {
            try
            {
                if (p.Statement.audio == p.Clip) p.Statement.audio = null;   // nur den eigenen Clip entfernen
                if (_verbose) _log.Msg($"[Bark] Aussage freigegeben ({(started ? "Clip spielt" : "Zeitüberschreitung")}): {p.Clip?.name}");
            }
            catch (Exception e) { _log.Warning($"Aussage freigeben: {e.GetType().Name}: {e.Message}"); }
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
                    if (source != null) { source.volume = t.OriginalVolume; _ids.Remove(source.GetInstanceID()); }
                    _tracked.RemoveAt(i);
                    continue;
                }
                if (!havePlayer) continue;   // Spieler unbekannt: nicht neu regeln; der Bark behält den zuletzt gesetzten Wert
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
            _log.Warning("Bark-Entfernung: Spielerposition nicht lesbar; laufende Barks behalten die zuletzt gesetzte Lautstärke.");
        }
    }
}
