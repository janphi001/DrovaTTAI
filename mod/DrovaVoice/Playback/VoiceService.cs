using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Playback
{
    /// <summary>Zentrale Stelle der Wiedergabe: ID -> Index -> Cache oder Laden. Fehlschläge werden gemerkt und nur einmal geloggt.</summary>
    internal sealed class VoiceService
    {
        private readonly AudioIndex _index;
        private readonly VoiceSettings _settings;
        private readonly ClipStore _store;
        private readonly ClipLoader _loader;
        private readonly MelonLogger.Instance _log;
        private readonly HashSet<string> _failed = new HashSet<string>(StringComparer.Ordinal);
        private readonly OnceLog _onceLog = new OnceLog();

        public VoiceService(AudioIndex index, string audioRoot, VoiceSettings settings, MelonLogger.Instance log)
        {
            _index = index;
            _settings = settings;
            _log = log;
            _store = new ClipStore(settings.CacheBytes);
            _loader = new ClipLoader(audioRoot);
        }

        public AudioClip? GetClip(string? id)
        {
            if (string.IsNullOrEmpty(id)) return null;
            if (!_index.TryGet(id, out var entry))
            {
                if (_settings.Diagnostics && _onceLog.ShouldLog("miss|" + id)) _log.Msg($"[Zeile] ohne Eintrag: {id}");
                return null;
            }
            if (_store.TryGet(id!, out var cached)) return cached;
            if (_failed.Contains(id!)) return null;

            var clip = _loader.Load(id!, entry, _settings.PercentFor(entry.Category), out long bytes, out string? error);
            if (clip == null)
            {
                _failed.Add(id!);
                if (_onceLog.ShouldLog("fail|" + id)) _log.Warning($"Zeile bleibt stumm ({error}): {id}");
                return null;
            }
            _store.Put(id!, clip, bytes);
            if (_settings.Diagnostics && _onceLog.ShouldLog("hit|" + id))
                _log.Msg($"[Zeile] geladen: {id} ({entry.File}, {entry.Duration:0.00} s, {entry.Category}); Cache {_store.Count} Clips, {_store.TotalBytes / 1024 / 1024} MB");
            return clip;
        }

        public void LogError(string where, Exception e)
        {
            if (_onceLog.ShouldLog("err|" + where + "|" + e.GetType().Name))
                _log.Error($"{where}: {e.GetType().Name}: {e.Message}");
        }
    }
}
