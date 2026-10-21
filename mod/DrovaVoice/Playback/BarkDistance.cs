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
    /// Zwei Aufgaben (Freigabe für alle Zeilen, Entfernung nur für Barks); Barks und Poolzeilen (generische Figuren) teilen die Aussage mit anderen Figuren:
    /// 1. <b>Aussage freigeben:</b> Hängt der Connector einen Clip an <c>statement.audio</c>, bleibt er dort stehen; bei jeder
    ///    Wiederholung ruft die API den Connector nicht mehr auf, und eine andere Figur spielte die Stimme der ersten (auch mit
    ///    falschem Geschlecht). Sobald der Clip abspielt (oder nach <see cref="TimeoutSeconds"/> Sekunden), wird <c>statement.audio</c>
    ///    wieder auf null gesetzt, damit der Connector bei der nächsten Ausführung neu entscheidet.
    /// 2. <b>Entfernung:</b> Spielt ein Bark-Clip (Clipname <c>DrovaVoice/bark/…</c>), regelt die Klasse in jedem Frame
    ///    <c>AudioSource.volume</c> nach <see cref="BarkAttenuation"/> (nah laut, weiter weg leiser, wieder lauter beim Annähern).
    ///    Die AudioSources kommen aus der gemeinsamen Suche (<see cref="AudioSourceScan"/>), nicht aus einer eigenen.
    ///    Am Ende wird die ursprüngliche Lautstärke wiederhergestellt, weil dieselbe Quelle später normale Dialoge spielt.
    ///    Ist die Spielerposition nicht lesbar, wird nichts neu geregelt: Ein laufender Bark behält den zuletzt gesetzten Wert.
    /// </summary>
    internal sealed class BarkDistance
    {
        public const string BarkClipPrefix = ClipLoader.ClipNamePrefix + "bark/";
        private const float TimeoutSeconds = 1.5f;   // Zeit statt Frames: unabhängig von der Bildrate

        private sealed class Tracked { public AudioSource Source = null!; public float OriginalVolume; public int ClipId; }
        private sealed class Pending { public DS_Statement Statement = null!; public AudioClip Clip = null!; public float Since; public string Name = ""; }

        private float _min, _max;
        private readonly MelonLogger.Instance _log;
        private readonly bool _verbose;
        private readonly List<Tracked> _tracked = new List<Tracked>();
        private readonly HashSet<int> _ids = new HashSet<int>();
        private readonly List<Pending> _pending = new List<Pending>();
        private bool _warnedNoPlayer;
        private readonly HashSet<string> _warned = new HashSet<string>();

        public BarkDistance(float min, float max, MelonLogger.Instance log, bool verbose)
        {
            _min = min; _max = max; _log = log; _verbose = verbose;
        }

        public void SetRange(float min, float max) { _min = min; _max = max; }

        public bool Busy => _pending.Count > 0 || _tracked.Count > 0;

        /// <summary>Der Connector hat <paramref name="clip"/> an die Aussage gehängt; sie wird freigegeben, sobald er abspielt.</summary>
        public void Watch(DS_Statement statement, AudioClip clip) =>
            _pending.Add(new Pending { Statement = statement, Clip = clip, Since = Time.unscaledTime, Name = SafeName(clip) });

        /// <summary>
        /// <paramref name="sources"/> ist die gemeinsame, gedrosselte Liste aus <see cref="AudioSourceScan"/>.
        /// Die Lautstärke läuft trotzdem in jedem Frame; nur die Suche selbst ist gedrosselt.
        /// </summary>
        public void Update(AudioSource[] sources, float now)
        {
            if (_pending.Count > 0) Guard("Freigabe", () => ResolvePending(sources, now));
            if (_tracked.Count > 0) Guard("Regelung", Apply);
        }

        /// <summary>Fehler je Abschnitt getrennt abfangen und je Art nur einmal loggen; ein dauerhafter Fehler soll das Log nicht fluten.</summary>
        private void Guard(string what, Action action)
        {
            try { action(); }
            catch (Exception e)
            {
                if (_warned.Add(what)) _log.Warning($"Bark-{what}: {e.GetType().Name}: {e.Message}");
            }
        }

        private void ResolvePending(AudioSource[] sources, float now)
        {
            var playing = new List<AudioSource>();
            if (sources != null)
            {
                foreach (var source in sources)
                {
                    try
                    {
                        if (source == null || !source.isPlaying || source.clip == null) continue;
                        playing.Add(source);
                        var clip = source.clip;
                        if (clip.name == null || !clip.name.StartsWith(BarkClipPrefix, StringComparison.Ordinal)) continue;
                        if (!_ids.Add(source.GetInstanceID())) continue;
                        _tracked.Add(new Tracked { Source = source, OriginalVolume = source.volume, ClipId = clip.GetInstanceID() });
                        if (_verbose) _log.Msg($"[Bark] Entfernungsregelung für {clip.name} (Lautstärke vorher {source.volume:0.00})");
                    }
                    catch (Exception e)
                    {
                        if (_warned.Add("Suche")) _log.Warning($"Bark-Suche: {e.GetType().Name}: {e.Message}");
                    }
                }
            }
            for (int i = _pending.Count - 1; i >= 0; i--)
            {
                var p = _pending[i];
                bool started = false;
                try { foreach (var s in playing) if (s.clip == p.Clip) { started = true; break; } }
                catch (Exception) { /* Quelle oder Clip zerstört: gilt als nicht gestartet, der Timeout greift */ }
                if (!started && now - p.Since < TimeoutSeconds) continue;
                Release(p, started);
                _pending.RemoveAt(i);   // immer entfernen, auch nach einem Fehler: _pending darf nicht wachsen
            }
        }

        private void Release(Pending p, bool started)
        {
            try
            {
                if (p.Statement.audio == p.Clip) p.Statement.audio = null;   // nur den eigenen Clip entfernen
                if (_verbose) _log.Msg($"[Bark] Aussage freigegeben ({(started ? "Clip spielt" : "Zeitüberschreitung")}): {p.Name}");
            }
            catch (Exception e) { if (_warned.Add("Aussage")) _log.Warning($"Aussage freigeben: {e.GetType().Name}: {e.Message}"); }
        }

        private static string SafeName(AudioClip clip)
        {
            try { return clip.name ?? ""; } catch (Exception) { return ""; }
        }

        private void Apply()
        {
            bool havePlayer = TryPlayerPosition(out Vector2 player);
            BarkPass.Run(
                _tracked,
                havePlayer,
                t => ReadSample(t, havePlayer, player),
                Drop,
                (t, distance) => t.Source.volume = t.OriginalVolume * BarkAttenuation.Gain(distance, _min, _max));
            if (_tracked.Count == 0) _ids.Clear();
        }

        private static BarkSample ReadSample(Tracked t, bool havePlayer, Vector2 player)
        {
            var source = t.Source;
            if (source == null) return new BarkSample();
            var clip = source.isPlaying ? source.clip : null;
            bool bark = false;
            if (clip != null)
            {
                // Name nur, wenn der Clip wechselt. Dieselbe Instanz bleibt ohne neue Zeichenkette geregelt.
                int clipId = clip.GetInstanceID();
                if (BarkTrack.SameClip(t.ClipId, clipId)) bark = true;
                else if ((clip.name ?? "").StartsWith(BarkClipPrefix, StringComparison.Ordinal))
                {
                    t.ClipId = clipId;
                    bark = true;
                }
            }
            if (!bark || !havePlayer) return new BarkSample { Active = bark };
            var pos = source.transform.position;
            float distance = Vector2.Distance(player, new Vector2(pos.x, pos.y));
            return new BarkSample { Active = true, Distance = distance };
        }

        private void Drop(Tracked t)
        {
            var source = t.Source;
            if (source == null) return;
            int id = source.GetInstanceID();
            try { source.volume = t.OriginalVolume; }
            finally { _ids.Remove(id); }
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
