using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using DrovaVoice.Core;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>Zentrale Stelle der Wiedergabe: ID -> Index -> Cache oder Laden. Fehlschläge werden gemerkt und nur einmal geloggt.</summary>
    internal sealed class VoiceService
    {
        private readonly AudioIndex _index;
        private VoiceSettings _settings;
        private readonly ClipStore _store;
        private readonly ClipLoader _loader;
        private readonly DecodeCache _decodes = new DecodeCache();
        private readonly MelonLogger.Instance _log;
        private readonly HashSet<string> _failed = new HashSet<string>(StringComparer.Ordinal);
        private readonly OnceLog _lineLog = new OnceLog();   // Diagnose je Zeile (miss/hit)
        private readonly OnceLog _problemLog = new OnceLog(); // Warnungen und Fehler, eigene Obergrenze

        public VoiceService(AudioIndex index, string audioRoot, VoiceSettings settings, MelonLogger.Instance log)
        {
            _index = index;
            _settings = settings;
            BaseSettings = settings;
            _log = log;
            _store = new ClipStore(settings.CacheBytes);
            _loader = new ClipLoader(audioRoot);
        }

        public bool Diagnostics => _settings.Diagnostics;
        public VoiceSettings Settings => _settings;
        /// <summary>Einstellungen aus MelonPreferences beim Start (Grundlage für die Menüwerte).</summary>
        public VoiceSettings BaseSettings { get; }

        /// <summary>Tauscht die Einstellungen aus (Optionsmenü). Gibt zurück, was sich geändert hat; Clips bleiben im Cache, ihr Schlüssel enthält die Lautstärke.</summary>
        public SettingsChange Apply(VoiceSettings next)
        {
            var change = VoiceSettings.Diff(_settings, next);
            _settings = next;
            if ((change & SettingsChange.Range) != 0) BarkDistance?.SetRange(next.BarkMinDistance, next.BarkMaxDistance);
            return change;
        }

        public bool ProbeFigures { get; set; }
        public float BarkMinDistance => _settings.BarkMinDistance;
        public float BarkMaxDistance => _settings.BarkMaxDistance;
        public BarkDistance? BarkDistance { get; set; }

        public void Probe(string key, string message)
        {
            if (ProbeFigures && _lineLog.ShouldLog("probe|" + key)) _log.Msg(message);
        }

        /// <summary>True, wenn die Zeile keinen eigenen Eintrag, aber Poolvarianten hat (generische Figur).</summary>
        public bool IsPoolLine(string id) => !HasEntry(id) && _index.PoolVariants(id).Count > 0;

        /// <summary>True, wenn die Zeile (oder ihre neutrale Variante) einen eigenen Eintrag hat, also keine Poolstimme gewählt werden muss.</summary>
        public bool HasEntry(string id) => _index.ResolveVariant(id, LineIds.NeutralVariant) is string r && _index.TryGet(r, out _);

        public AudioClip? GetClip(string? id, FigureInfo? figure = null)
        {
            if (!_settings.Enabled) return null;
            id = _index.ResolveVariant(id, LineIds.NeutralVariant);
            id = PoolVoice.Resolve(_index, id, figure);
            if (string.IsNullOrEmpty(id)) return null;
            if (!_index.TryGet(id, out var entry))
            {
                Diag("miss|" + id, $"[Zeile] ohne Eintrag: {id}");
                return null;
            }
            int percent = _settings.PercentFor(entry.Category);
            string cacheKey = id + "@" + percent;   // andere Lautstärke = anderer Schlüssel; alte Clips altern aus dem Cache
            if (_store.TryGet(cacheKey, out var cached)) return cached;
            if (_failed.Contains(id!)) return null;

            var watch = Stopwatch.StartNew();
            var status = AwaitSamples(cacheKey, entry, percent, out var decoded, out string? error);
            if (status != DecodeStatus.Ready || decoded == null)
            {
                // Eine Zeitüberschreitung ist vorübergehend (kalte Platte, Last): beim nächsten Mal neu versuchen.
                if (error != DecodeCache.TimeoutError) _failed.Add(id!);
                _decodes.TryRemove(cacheKey, out _, out _);
                Problem("fail|" + id, $"Zeile bleibt stumm ({error ?? "Dekodieren fehlgeschlagen"}): {id}", error: false);
                return null;
            }
            var clip = _loader.CreateClip(entry, decoded, out error);
            watch.Stop();
            long elapsedMs = watch.ElapsedMilliseconds;
            _decodes.TryRemove(cacheKey, out _, out _);
            if (clip == null)
            {
                _failed.Add(id!);
                Problem("fail|" + id, $"Zeile bleibt stumm ({error}): {id}", error: false);
                return null;
            }
            _store.Put(cacheKey, clip, decoded.Bytes);
            if (elapsedMs > ClipLoader.SlowMilliseconds) Problem("slow|" + id, $"Laden dauerte {elapsedMs} ms (Ruckler möglich): {id}", error: false);
            Diag("hit|" + cacheKey, $"[Zeile] geladen: {id} ({entry.File}, {entry.Duration:0.00} s, {entry.Category}, {percent} %, {elapsedMs} ms); Cache {_store.Count} Clips, {_store.TotalBytes / 1024 / 1024} MB");
            return clip;
        }

        /// <summary>
        /// Dekodiert im ThreadPool und wartet hier auf das PCM. Unity (<c>AudioClip</c>) läuft erst danach, auf diesem Thread.
        /// Der Worker darf kein Unity anfassen. Der Connector braucht den Clip, bevor er zurückkehrt.
        /// </summary>
        private DecodeStatus AwaitSamples(string key, IndexEntry entry, int percent, out DecodedClip? decoded, out string? error)
        {
            var status = _decodes.Peek(key, out decoded, out error);
            if (status == DecodeStatus.Ready || status == DecodeStatus.Failed) return status;
            if (status == DecodeStatus.Missing && _decodes.TryBegin(key))
            {
                var captured = entry;
                int capturedPercent = percent;
                ThreadPool.QueueUserWorkItem(_ => DecodeWorker(key, captured, capturedPercent));
            }
            return _decodes.Wait(key, ClipLoader.DecodeWait, out decoded, out error);
        }

        private void DecodeWorker(string key, IndexEntry entry, int percent)
        {
            try
            {
                var pcm = _loader.Decode(entry, percent);
                if (pcm.Samples == null)
                {
                    _decodes.Fail(key, string.IsNullOrEmpty(pcm.Error) ? "Dekodieren fehlgeschlagen" : pcm.Error!);
                    return;
                }
                _decodes.Complete(key, new DecodedClip(pcm.Samples, pcm.Channels, pcm.SampleRate, pcm.ElapsedMilliseconds));
            }
            catch (Exception e)
            {
                try { _decodes.Fail(key, e.GetType().Name + ": " + e.Message); } catch (Exception) { }
            }
        }

        /// <summary>
        /// Auswahloption: erst die exakte ID (Baum|Pfad|Schlüssel|c&lt;k&gt;); passt <c>k</c> nicht mehr zum Export, weil das Spiel die
        /// Optionsliste verändert hat, gilt der einzige Auswahl-Eintrag mit demselben Schlüssel.
        /// </summary>
        public AudioClip? GetChoiceClip(string statementId, string choiceId)
        {
            if (_index.TryGet(choiceId, out _)) return GetClip(choiceId);
            if (_index.TryGetUniqueChoice(statementId, out string alternative, out _))
            {
                Diag("alt|" + choiceId, $"[Zeile] Option {choiceId} -> {alternative} (Index der Option hat sich verschoben)");
                return GetClip(alternative);
            }
            return GetClip(choiceId);   // meldet den Fehltreffer
        }

        public void Diag(string key, string message)
        {
            if (_settings.Diagnostics && _lineLog.ShouldLog(key)) _log.Msg(message);
        }

        public void Problem(string key, string message, bool error)
        {
            if (!_problemLog.ShouldLog(key)) return;
            if (error) _log.Error(message); else _log.Warning(message);
        }

        public void LogError(string where, string? id, Exception e) =>
            Problem("err|" + where + "|" + id + "|" + e.GetType().Name, $"{where}: {e.GetType().Name}: {e.Message} (Zeile: {id ?? "?"})", error: true);
    }
}
