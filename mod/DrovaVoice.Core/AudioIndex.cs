using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace DrovaVoice.Core
{
    public enum VoiceCategory { Dialog, Player, Bark }

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
        private readonly Dictionary<string, List<string>> _choiceIdsByStatement;
        private readonly Dictionary<string, List<string>> _poolVariants;

        private AudioIndex(Dictionary<string, IndexEntry> entries, int skipped)
        {
            _entries = entries;
            Skipped = skipped;
            _choiceIdsByStatement = BuildChoiceLookup(entries.Keys);
            _poolVariants = BuildPoolLookup(entries.Keys);
        }

        public int Count => _entries.Count;
        public int Skipped { get; }

        public bool TryGet(string? id, out IndexEntry entry)
        {
            if (!string.IsNullOrEmpty(id) && _entries.TryGetValue(id!, out var found)) { entry = found; return true; }
            entry = null!;
            return false;
        }

        /// <summary>
        /// Liefert <c>id#variant</c>, wenn der Index diese Variante hat, sonst <paramref name="id"/> unverändert
        /// (leere oder fehlende IDs gehen durch). So spielt die Mod bei Zeilen mit Spielernamen die neutrale Fassung.
        /// </summary>
        public string? ResolveVariant(string? id, string variant)
        {
            if (string.IsNullOrEmpty(id)) return id;
            string withVariant = LineIds.WithVariant(id!, variant);
            return _entries.ContainsKey(withVariant) ? withVariant : id;
        }

        /// <summary>
        /// Fallback für Auswahloptionen: Verschiebt das Spiel die Optionsliste (einmalige Optionen, "Zurück"), passt der
        /// Index <c>k</c> nicht mehr zum Export. Der Schlüssel der Zeile bestimmt den Text eindeutig; gibt es zu
        /// <paramref name="statementId"/> (Baum|Pfad|Schlüssel) genau einen Auswahl-Eintrag, ist es die gesuchte Zeile.
        /// </summary>
        public bool TryGetUniqueChoice(string? statementId, out string choiceId, out IndexEntry entry)
        {
            choiceId = string.Empty;
            entry = null!;
            if (string.IsNullOrEmpty(statementId)) return false;
            if (!_choiceIdsByStatement.TryGetValue(statementId!, out var ids) || ids.Count != 1) return false;
            choiceId = ids[0];
            entry = _entries[choiceId];
            return true;
        }

        /// <summary>Poolvarianten (vm1, vw2 …) einer Basis-ID, sortiert; leer, wenn es keine gibt.</summary>
        public IReadOnlyList<string> PoolVariants(string? id) =>
            !string.IsNullOrEmpty(id) && _poolVariants.TryGetValue(id!, out var list) ? list : Array.Empty<string>();

        private static Dictionary<string, List<string>> BuildPoolLookup(IEnumerable<string> ids)
        {
            var map = new Dictionary<string, List<string>>(StringComparer.Ordinal);
            foreach (string id in ids)
            {
                int cut = id.LastIndexOf(LineIds.VariantSeparator);
                if (cut <= 0) continue;
                string tag = id.Substring(cut + 1);
                if (!PoolVoice.IsPoolTag(tag)) continue;
                string baseId = id.Substring(0, cut);
                if (!map.TryGetValue(baseId, out var list)) map[baseId] = list = new List<string>();
                list.Add(tag);
            }
            foreach (var list in map.Values) list.Sort(StringComparer.Ordinal);
            return map;
        }

        private static Dictionary<string, List<string>> BuildChoiceLookup(IEnumerable<string> ids)
        {
            var map = new Dictionary<string, List<string>>(StringComparer.Ordinal);
            foreach (string id in ids)
            {
                if (id.IndexOf(LineIds.VariantSeparator) >= 0) continue;          // Varianten zählen nicht
                int cut = id.LastIndexOf(LineIds.Separator);
                if (cut < 0 || cut + 2 > id.Length || id[cut + 1] != 'c') continue;
                bool digits = id.Length > cut + 2;
                for (int i = cut + 2; i < id.Length; i++) if (id[i] < '0' || id[i] > '9') { digits = false; break; }
                if (!digits) continue;
                string statementId = id.Substring(0, cut);
                if (!map.TryGetValue(statementId, out var list)) map[statementId] = list = new List<string>();
                list.Add(id);
            }
            return map;
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
            file.StartsWith("player/", StringComparison.Ordinal) ? VoiceCategory.Player
            : file.StartsWith("bark/", StringComparison.Ordinal) ? VoiceCategory.Bark
            : VoiceCategory.Dialog;

        /// <summary>Relativ, mit '/', ohne '..', ohne Laufwerk, ohne Rückwärtsstrich, ohne Windows-Gerätenamen.</summary>
        public static bool IsSafeRelativePath(string file)
        {
            if (string.IsNullOrEmpty(file)) return false;
            if (file.IndexOf('\\') >= 0 || file.IndexOf(':') >= 0 || file[0] == '/') return false;
            foreach (string part in file.Split('/'))
            {
                if (part.Length == 0 || part == "." || part == "..") return false;
                // CON, AUX und COM1 blockieren auf Windows beim Öffnen den Thread. Ein Punkt oder Leerzeichen am Ende
                // wird dort abgeschnitten, der geöffnete Name ist dann ein anderer.
                if (IsReservedDevice(part)) return false;
            }
            return true;
        }

        private static bool IsReservedDevice(string segment)
        {
            if (segment[segment.Length - 1] == '.' || segment[segment.Length - 1] == ' ') return true;
            int dot = segment.IndexOf('.');
            string stem = dot >= 0 ? segment.Substring(0, dot) : segment;
            if (stem.Length == 0) return true;
            if (stem.Equals("CON", StringComparison.OrdinalIgnoreCase)
                || stem.Equals("PRN", StringComparison.OrdinalIgnoreCase)
                || stem.Equals("AUX", StringComparison.OrdinalIgnoreCase)
                || stem.Equals("NUL", StringComparison.OrdinalIgnoreCase))
                return true;
            if (stem.Length != 4) return false;
            if (!stem.StartsWith("COM", StringComparison.OrdinalIgnoreCase)
                && !stem.StartsWith("LPT", StringComparison.OrdinalIgnoreCase))
                return false;
            return stem[3] >= '1' && stem[3] <= '9';
        }

        public static string? ResolvePath(string root, string file) =>
            IsSafeRelativePath(file) ? Path.Combine(root, file.Replace('/', Path.DirectorySeparatorChar)) : null;
    }
}
