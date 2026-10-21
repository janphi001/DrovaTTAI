using System.Collections.Generic;
using System.Text.Json;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Zeilen, die das Spiel ausführt, für die der Index aber keinen Eintrag hat (z. B. Vorlagen-Bäume wie
    /// <c>DT_WorldDialogue_Template</c>, deren Loca-Pfad erst zur Laufzeit feststeht und die der Export im Hauptmenü nicht sieht).
    /// Die Mod hängt jede solche Zeile einmal an <see cref="FileName"/> im Export-Ordner an (eine Manifestzeile je Textzeile);
    /// <c>drova-voice extract</c> nimmt die Datei zum Manifest dazu. Bereits vorhandene IDs werden nicht noch einmal geschrieben.
    /// </summary>
    public sealed class RuntimeLineLog
    {
        public const string FileName = "manifest-runtime.jsonl";

        private readonly HashSet<string> _known = new HashSet<string>(System.StringComparer.Ordinal);

        /// <summary><paramref name="existing"/>: Zeilen der vorhandenen Datei; unlesbare Zeilen werden übergangen.</summary>
        public RuntimeLineLog(IEnumerable<string> existing)
        {
            foreach (string raw in existing)
            {
                if (string.IsNullOrWhiteSpace(raw)) continue;
                try
                {
                    var line = ManifestJson.DeserializeLine(raw);
                    if (line != null && !string.IsNullOrEmpty(line.Id)) _known.Add(line.Id);
                }
                catch (JsonException) { /* angeschnittene Zeile nach Absturz: übergehen */ }
            }
        }

        public int Count => _known.Count;

        public bool Contains(string id) => _known.Contains(id);

        /// <summary>Die anzuhängende JSON-Zeile, oder null, wenn die ID schon bekannt ist.</summary>
        public string? Add(ManifestLine line)
        {
            if (string.IsNullOrEmpty(line.Id) || !_known.Add(line.Id)) return null;
            return ManifestJson.SerializeLine(line);
        }
    }
}
