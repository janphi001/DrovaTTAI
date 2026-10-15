using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Wählt für generische Figuren eine Poolstimme (Variante vm1, vw2 …). Die Wahl hängt nur von Figurschlüssel
    /// (oder Zeilen-ID, wenn die Figur nicht lesbar ist) und der Variantenliste ab, damit sie über Sitzungen stabil ist.
    /// </summary>
    public static class PoolVoice
    {
        public static bool IsPoolTag(string? tag)
        {
            if (string.IsNullOrEmpty(tag) || tag!.Length < 3 || tag[0] != 'v' || (tag[1] != 'm' && tag[1] != 'w')) return false;
            for (int i = 2; i < tag.Length; i++) if (tag[i] < '0' || tag[i] > '9') return false;
            return true;
        }

        /// <summary>FNV-1a, 32 Bit, über die UTF-8-Bytes.</summary>
        public static uint Fnv1a(string text)
        {
            uint hash = 2166136261u;
            foreach (byte b in Encoding.UTF8.GetBytes(text ?? string.Empty)) { hash ^= b; hash *= 16777619u; }
            return hash;
        }

        public static string? Pick(IReadOnlyList<string> tags, char? gender, string? figureKey, string lineId)
        {
            var pool = tags.Where(IsPoolTag).OrderBy(t => t, StringComparer.Ordinal).ToList();
            if (pool.Count == 0) return null;
            if (gender is char g)
            {
                var matching = pool.Where(t => t[1] == g).ToList();
                if (matching.Count > 0) pool = matching;
            }
            string key = string.IsNullOrEmpty(figureKey) ? lineId : figureKey!;
            return pool[(int)(Fnv1a(key) % (uint)pool.Count)];
        }

        /// <summary>Die ID, die gespielt werden soll: die Basis-ID, wenn sie einen Eintrag hat, sonst die gewählte Poolvariante.</summary>
        public static string? Resolve(AudioIndex index, string? id, FigureInfo? figure)
        {
            if (string.IsNullOrEmpty(id) || index.TryGet(id, out _)) return id;
            string? tag = Pick(index.PoolVariants(id), figure?.Gender, figure?.Key, id!);
            return tag == null ? id : LineIds.WithVariant(id!, tag);
        }

        public static char? GenderFromBodyType(string? bodyType) => bodyType switch
        {
            "Strong" => 'm',
            "Petite" => 'w',
            _ => null,
        };
    }
}
