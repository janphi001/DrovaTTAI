using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace DrovaVoice.Core
{
    public enum VoiceCategory { Dialog, Player }

    public sealed record IndexEntry(string File, double Duration, VoiceCategory Category);

    public sealed class IndexFormatException : Exception
    {
        public IndexFormatException(string message) : base(message) { }
    }

    /// <summary>
    /// Liest Audio/&lt;Sprache&gt;/index.json (Vertrag: docs/audio-format.md). Die Mod bildet keine Dateinamen selbst,
    /// sie schlägt nur die volle Zeilen-ID nach. Kaputte Einträge werden übersprungen und gezählt, nicht gemeldet.
    /// </summary>
    public sealed class AudioIndex
    {
        public const int SupportedVersion = 1;
        private readonly Dictionary<string, IndexEntry> _entries;

        private AudioIndex(Dictionary<string, IndexEntry> entries, int skipped)
        {
            _entries = entries;
            Skipped = skipped;
        }

        public int Count => _entries.Count;
        public int Skipped { get; }

        public bool TryGet(string? id, out IndexEntry entry)
        {
            if (!string.IsNullOrEmpty(id) && _entries.TryGetValue(id!, out var found)) { entry = found; return true; }
            entry = null!;
            return false;
        }

        public static AudioIndex Parse(string json, string expectedLanguage)
        {
            JsonDocument doc;
            try { doc = JsonDocument.Parse(json); }
            catch (JsonException e) { throw new IndexFormatException("index.json ist kein gültiges JSON: " + e.Message); }
            using (doc)
            {
                var root = doc.RootElement;
                if (root.ValueKind != JsonValueKind.Object) throw new IndexFormatException("index.json: Wurzel ist kein Objekt");
                if (!root.TryGetProperty("version", out var version) || version.ValueKind != JsonValueKind.Number
                    || !version.TryGetInt32(out int v) || v != SupportedVersion)
                    throw new IndexFormatException($"index.json: Version fehlt oder ist nicht {SupportedVersion}");
                string? language = root.TryGetProperty("language", out var lang) && lang.ValueKind == JsonValueKind.String ? lang.GetString() : null;
                if (!string.Equals(language, expectedLanguage, StringComparison.OrdinalIgnoreCase))
                    throw new IndexFormatException($"index.json: Sprache '{language}' passt nicht zu '{expectedLanguage}'");
                if (!root.TryGetProperty("entries", out var entries) || entries.ValueKind != JsonValueKind.Object)
                    throw new IndexFormatException("index.json: 'entries' fehlt");

                var map = new Dictionary<string, IndexEntry>(StringComparer.Ordinal);
                int skipped = 0;
                foreach (var prop in entries.EnumerateObject())
                {
                    var value = prop.Value;
                    if (value.ValueKind != JsonValueKind.Object
                        || !value.TryGetProperty("file", out var fileEl) || fileEl.ValueKind != JsonValueKind.String)
                    { skipped++; continue; }
                    string file = fileEl.GetString() ?? "";
                    if (!IsSafeRelativePath(file)) { skipped++; continue; }
                    double duration = value.TryGetProperty("duration", out var d) && d.ValueKind == JsonValueKind.Number ? d.GetDouble() : 0.0;
                    map[prop.Name] = new IndexEntry(file, duration, CategoryOf(file));
                }
                return new AudioIndex(map, skipped);
            }
        }

        public static VoiceCategory CategoryOf(string file) =>
            file.StartsWith("player/", StringComparison.Ordinal) ? VoiceCategory.Player : VoiceCategory.Dialog;

        /// <summary>Relativ, mit '/', ohne '..', ohne Laufwerk, ohne Rückwärtsstrich.</summary>
        public static bool IsSafeRelativePath(string file)
        {
            if (string.IsNullOrEmpty(file)) return false;
            if (file.IndexOf('\\') >= 0 || file.IndexOf(':') >= 0 || file[0] == '/') return false;
            foreach (string part in file.Split('/'))
                if (part.Length == 0 || part == "." || part == "..") return false;
            return true;
        }

        public static string? ResolvePath(string root, string file) =>
            IsSafeRelativePath(file) ? Path.Combine(root, file.Replace('/', Path.DirectorySeparatorChar)) : null;
    }
}
