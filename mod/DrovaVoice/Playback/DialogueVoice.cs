using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using HarmonyLib;
using MelonLoader;
using UnityEngine;
using Il2CppUi = Il2CppNodeCanvas.DialogueTrees.UI;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Spielt Dialog- und Spielerzeilen auf einer eigenen AudioSource am Dialog-Objekt des Sprechers, statt den Clip an
    /// <c>statement.audio</c> zu hängen. Hängt dort ein Clip, behandelt das Dialogfeld des Spiels die Stimme beim Skip als eigene
    /// Stufe: Der erste Druck beendet nur die Stimme, der Text tippt in normaler Geschwindigkeit weiter (im Spiel gemessen).
    /// Ohne Clip skippt das Spiel wie im Original. Diese Klasse übernimmt deshalb Start und Ende der Stimme selbst:
    /// Start, wenn das Dialogfeld die Zeile anfragt (<c>OnSubtitlesRequest</c>, im selben Bild wie der Connector);
    /// Ende bei der nächsten Zeile desselben Dialogfelds, beim Ende oder der Pause des Gesprächs und bei einem Tastendruck
    /// (Skip). Einstellungen (3D, Reichweite, Mixer) kommen von der Quelle des Spiels am selben Objekt.
    /// Barks laufen weiter über <c>statement.audio</c>: Sie haben keinen Skip, und <see cref="BarkDistance"/> regelt sie.
    /// <para>Tempo: Mit Clip an der Aussage tippt das Spiel den Text über die Clip-Länge (Text endet mit der Stimme); ohne Clip
    /// tippt es etwa 70 Zeichen pro Sekunde. Solange die Stimme läuft, begrenzt <see cref="LateUpdate"/> deshalb die sichtbaren
    /// Zeichen im Gesprächsfenster auf den Anteil der abgelaufenen Clip-Zeit (nach dem Spiel im selben Bild, also gilt dieser Wert).
    /// Endet die Stimme oder wird sie per Taste beendet, lässt die Mod los: Das Spiel zeigt seinen Stand (meist schon vollständig),
    /// ein weiterer Druck schaltet wie im Spiel weiter.</para>
    /// </summary>
    internal sealed class DialogueVoice
    {
        /// <summary>So viele Bilder darf die Anfrage des Dialogfelds nach dem Connector kommen (im Spiel: dasselbe Bild).</summary>
        private const int PendingFrames = 2;

        /// <summary>Ein Tastendruck so kurz nach dem Start gehört zum Start (Gespräch beginnen, Zeile weiterschalten), nicht zum Skip.</summary>
        private const float StartGraceSeconds = 0.25f;

        private static DialogueVoice? _current;

        private readonly MelonLogger.Instance _log;
        private readonly bool _verbose;
        private readonly Dictionary<int, AudioSource> _own = new Dictionary<int, AudioSource>();
        private readonly OnceLog _faults = new OnceLog();
        private AudioClip? _pending;
        private int _pendingFrame;
        private AudioSource? _playing;
        private int _playingUi;
        private float _startedAt;
        private float _clipLength;
        private bool _ready;
        private Il2CppTMPro.TextMeshProUGUI? _paced;
        private int _gameVisible = int.MaxValue;   // letzter Wert, den das Spiel selbst geschrieben hat
        private int _written = -1;                 // letzter Wert der Mod
        private float _searchUntil;
        private int _nextSearchFrame;
        private readonly HashSet<string> _textsBefore = new HashSet<string>();

        /// <summary>So lange nach dem Start wird das Textfeld der Zeile gesucht (das Fenster blendet beim ersten Satz erst ein).</summary>
        private const float SearchSeconds = 1f;

        public DialogueVoice(MelonLogger.Instance log, bool verbose) { _log = log; _verbose = verbose; }

        public bool Ready => _ready;

        /// <summary>Legt die Patches von Hand an; Attribut-Patches auf verschachtelten Klassen greifen hier nicht.</summary>
        public void Install(HarmonyLib.Harmony harmony)
        {
            try
            {
                var type = typeof(Il2CppUi.DS_DialogueUGUI);
                var request = AccessTools.Method(type, "OnSubtitlesRequest");
                var finished = AccessTools.Method(type, "OnDialogueFinished");
                var paused = AccessTools.Method(type, "OnDialoguePaused");
                if (request == null || finished == null || paused == null)
                {
                    _log.Warning("Eigene Dialogstimme: Methoden des Dialogfelds nicht gefunden, Dialoge laufen wie bisher über das Spiel.");
                    return;
                }
                harmony.Patch(request, prefix: new HarmonyMethod(typeof(DialogueVoice), nameof(RequestPrefix)));
                harmony.Patch(finished, prefix: new HarmonyMethod(typeof(DialogueVoice), nameof(EndPrefix)));
                harmony.Patch(paused, prefix: new HarmonyMethod(typeof(DialogueVoice), nameof(EndPrefix)));
                _current = this;
                _ready = true;
                if (_verbose) _log.Msg("[Stimme] eigene Dialogstimme bereit");
            }
            catch (Exception e)
            {
                _ready = false;
                _log.Warning($"Eigene Dialogstimme: Patch fehlgeschlagen ({e.GetType().Name}: {e.Message}), Dialoge laufen wie bisher über das Spiel.");
            }
        }

        /// <summary>Der Connector hat einen Clip für die gerade ausgeführte Aussage. Er spielt, sobald das Dialogfeld die Zeile anfragt.</summary>
        public void Queue(AudioClip clip)
        {
            _pending = clip;
            _pendingFrame = Time.frameCount;
        }

        private static void RequestPrefix(object __instance)
        {
            try { _current?.OnRequest(__instance as Il2CppUi.DS_DialogueUGUI); }
            catch (Exception e) { _current?.Fault("Start", e); }
        }

        private static void EndPrefix(object __instance)
        {
            try
            {
                var self = _current;
                var ui = __instance as Il2CppUi.DS_DialogueUGUI;
                if (self == null || ui == null) return;
                if (ui.GetInstanceID() == self._playingUi) self.Stop("Gesprächsende");
            }
            catch (Exception e) { _current?.Fault("Ende", e); }
        }

        private void OnRequest(Il2CppUi.DS_DialogueUGUI? ui)
        {
            if (ui == null) return;
            int id = ui.GetInstanceID();
            if (id == _playingUi) Stop(null);   // nächste Zeile desselben Dialogfelds
            var clip = _pending;
            if (clip == null) return;
            if (Time.frameCount - _pendingFrame > PendingFrames) { _pending = null; return; }
            _pending = null;
            var source = OwnSource(ui);
            if (source == null) return;
            source.clip = clip;
            source.time = 0f;
            source.Play();
            _playing = source;
            _playingUi = id;
            _startedAt = Time.unscaledTime;
            _clipLength = clip.length;
            ReleaseText();   // ein anderes Dialogfeld kann noch ein Textfeld halten
            _searchUntil = _startedAt + SearchSeconds;
            _nextSearchFrame = Time.frameCount + 1;
            _textsBefore.Clear();
            foreach (var t in WindowTexts()) _textsBefore.Add(t.text ?? "");   // Text der vorigen Zeile ist nicht der neue
        }

        /// <summary>Nach dem Spiel im selben Bild: sichtbare Zeichen an die Stimme koppeln.</summary>
        public void LateUpdate(float now)
        {
            if (!_ready || _playing == null) return;
            try
            {
                var text = _paced;
                if (text == null)
                {
                    if (now > _searchUntil || Time.frameCount < _nextSearchFrame) return;
                    _nextSearchFrame = Time.frameCount + 3;   // Suche gedrosselt, nur kurz nach dem Start
                    foreach (var t in WindowTexts())
                    {
                        string content = t.text ?? "";
                        if (content.Length == 0 || _textsBefore.Contains(content)) continue;
                        _paced = text = t;
                        _gameVisible = int.MaxValue;
                        _written = -1;
                        break;
                    }
                    if (text == null) return;
                }
                if (text == null || !text.gameObject.activeInHierarchy || _clipLength <= 0f) { _paced = null; return; }
                int total = text.textInfo != null ? text.textInfo.characterCount : 0;
                if (total <= 0) return;
                int current = text.maxVisibleCharacters;
                if (current != _written) _gameVisible = current;   // das Spiel hat seit dem letzten Bild selbst geschrieben
                int want = Math.Min(TextPace.Visible(total, now - _startedAt, _clipLength), _gameVisible);
                if (want != current) { text.maxVisibleCharacters = want; _written = want; }
            }
            catch (Exception e) { _paced = null; Fault("Tempo", e); }
        }

        /// <summary>Loslassen: Hat seit dem letzten Bild niemand anders geschrieben, bekommt das Textfeld den Stand des Spiels zurück.</summary>
        private void ReleaseText()
        {
            var text = _paced;
            _paced = null;
            try
            {
                if (text != null && _written >= 0 && text.maxVisibleCharacters == _written && _gameVisible != int.MaxValue)
                    text.maxVisibleCharacters = _gameVisible;
            }
            catch (Exception e) { Fault("Tempo", e); }
            _written = -1;
            _gameVisible = int.MaxValue;
        }

        /// <summary>Aktive Textfelder des Gesprächsfensters (…/SubtitlesGroup/Speech, ohne Sprechblasen …/WorldBox/…).</summary>
        private static IEnumerable<Il2CppTMPro.TextMeshProUGUI> WindowTexts()
        {
            foreach (var t in UnityEngine.Object.FindObjectsOfType<Il2CppTMPro.TextMeshProUGUI>(false))
            {
                if (t == null || t.name != "Speech") continue;
                bool group = false, bubble = false;
                var tr = t.transform;
                for (int depth = 0; tr != null && depth < 6; depth++, tr = tr.parent)
                {
                    if (tr.name == "WorldBox") bubble = true;
                    if (tr.name == "SubtitlesGroup") group = true;
                }
                if (group && !bubble) yield return t;
            }
        }

        /// <summary>Einmal je Bild: ein Tastendruck während der Stimme beendet sie (Skip).</summary>
        public void Update(float now)
        {
            if (!_ready) return;
            try
            {
                if (_pending != null && Time.frameCount - _pendingFrame > PendingFrames) _pending = null;
                var source = _playing;
                if (source == null) return;
                if (!source.isPlaying) { _playing = null; _playingUi = 0; ReleaseText(); return; }
                if (now - _startedAt < StartGraceSeconds) return;
                bool key = false;
                try { key = Input.anyKeyDown || Input.GetMouseButtonDown(0); } catch (Exception) { /* ohne Eingabemodul endet die Stimme mit der Zeile */ }
                if (key) Stop("Taste");
            }
            catch (Exception e) { Fault("Taste", e); }
        }

        private void Stop(string? reason)
        {
            var source = _playing;
            _playing = null;
            _playingUi = 0;
            ReleaseText();
            if (source == null) return;
            bool wasPlaying = source.isPlaying;
            source.Stop();
            source.clip = null;
            if (_verbose && reason != null && wasPlaying) _log.Msg($"[Stimme] beendet ({reason})");
        }

        /// <summary>Eigene Quelle am Objekt des Dialogfelds; Einstellungen von der Quelle des Spiels dort.</summary>
        private AudioSource? OwnSource(Il2CppUi.DS_DialogueUGUI ui)
        {
            int id = ui.GetInstanceID();
            if (_own.TryGetValue(id, out var existing) && existing != null) return existing;
            var go = ui.gameObject;
            AudioSource? reference = null;
            foreach (var s in go.GetComponentsInChildren<AudioSource>(true))
            {
                if (s != null && !IsOwn(s)) { reference = s; break; }
            }
            var source = go.AddComponent<AudioSource>();
            source.playOnAwake = false;
            source.loop = false;
            source.volume = 1f;
            if (reference != null)
            {
                source.outputAudioMixerGroup = reference.outputAudioMixerGroup;
                source.spatialBlend = reference.spatialBlend;
                source.rolloffMode = reference.rolloffMode;
                source.minDistance = reference.minDistance;
                source.maxDistance = reference.maxDistance;
                source.dopplerLevel = reference.dopplerLevel;
                source.spread = reference.spread;
                source.priority = reference.priority;
                source.panStereo = reference.panStereo;
                source.pitch = reference.pitch;
            }
            _own[id] = source;
            if (_verbose) _log.Msg($"[Stimme] eigene Quelle an {go.name} ({(reference != null ? $"wie {reference.name}: 3D {reference.spatialBlend:0.00}, {reference.minDistance:0}-{reference.maxDistance:0}" : "ohne Vorlage")})");
            return source;
        }

        private bool IsOwn(AudioSource s)
        {
            foreach (var own in _own.Values) if (own != null && own == s) return true;
            return false;
        }

        private void Fault(string what, Exception e)
        {
            if (_faults.ShouldLog(what + e.GetType().Name)) _log.Warning($"Eigene Dialogstimme ({what}): {e.GetType().Name}: {e.Message}");
        }
    }
}
