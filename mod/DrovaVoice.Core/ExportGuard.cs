using System;
using System.Collections.Generic;
using System.Linq;

namespace DrovaVoice.Core
{
    /// <summary>Entscheidungslogik gegen Datenverlust: ein leerer oder fehlgeschlagener Export darf eine gute Ausgabedatei nie überschreiben.</summary>
    public static class ExportGuard
    {
        /// <summary>Null = speichern erlaubt, sonst der (deutsche) Grund, warum nicht gespeichert wird. <paramref name="addressCount"/> ist null, wenn es keine Katalog-Adressen gibt (Export nur geladener Bäume).</summary>
        public static string? ShouldSave(int lineCount, bool loaderGaveUp, int? addressCount)
        {
            if (addressCount.HasValue && addressCount.Value == 0) return "der Katalog enthält 0 Baum-Adressen";
            if (loaderGaveUp) return "das Laden der Bäume aus dem Katalog wurde abgebrochen";
            if (lineCount == 0) return "der Export enthält 0 Zeilen";
            return null;
        }

        /// <summary>Null = Liste darf geschrieben werden, sonst der Grund (leere Liste würde eine gute Datei überschreiben).</summary>
        public static string? ShouldWriteList(int itemCount)
            => itemCount == 0 ? "die Liste ist leer" : null;
    }

    /// <summary>Vergleich der Spielsprache mit der Export-Einstellung.</summary>
    public static class LanguageCheck
    {
        /// <summary>
        /// True, wenn Spielsprache und Einstellung gleich sind (ohne Groß-/Kleinschreibung). Die Werte des Spiel-Enums ELanguage
        /// heißen wie die Sprachordner (de, en, zh_CN, ...), die Einstellung ExportLanguage nutzt dieselben Kürzel.
        /// </summary>
        public static bool Matches(string currentLanguage, string preference)
        {
            string cur = (currentLanguage ?? "").Trim();
            string pref = (preference ?? "").Trim();
            return cur.Length > 0 && string.Equals(cur, pref, StringComparison.OrdinalIgnoreCase);
        }
    }

    /// <summary>Zählt nicht exportierte Knotentypen (nur .NET-Klassennamen, kein Spieltext).</summary>
    public static class NodeTypeCounts
    {
        public static string Summarize(IReadOnlyDictionary<string, int> counts, int top = 5)
        {
            if (counts.Count == 0) return "keine";
            var parts = counts.OrderByDescending(kv => kv.Value).ThenBy(kv => kv.Key, StringComparer.Ordinal)
                              .Take(top).Select(kv => $"{kv.Key} {kv.Value}");
            string text = string.Join(", ", parts);
            return counts.Count > top ? text + $", +{counts.Count - top} weitere Typen" : text;
        }
    }
}
