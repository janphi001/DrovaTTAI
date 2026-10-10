using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Zeilen-IDs und Audio-Dateinamen. Muss exakt drova_voice/ids.py entsprechen
    /// (geprüft über tests/vectors/line_ids.json).
    /// </summary>
    public static class LineIds
    {
        public const char Separator = '|';
        public const char VariantSeparator = '#';

        public static string NormalizeLocaPath(string? path) => (path ?? string.Empty).Replace('\\', '/').Trim('/');

        public static string Statement(string tree, string locaPath, string locaKey)
        {
            string path = NormalizeLocaPath(locaPath);
            RequireClean(tree, nameof(tree));
            RequireClean(path, nameof(locaPath));
            RequireClean(locaKey, nameof(locaKey));
            return string.Join(Separator, tree, path, locaKey);
        }

        public static string Choice(string tree, string locaPath, string locaKey, int choiceIndex)
        {
            if (choiceIndex < 0) throw new ArgumentOutOfRangeException(nameof(choiceIndex));
            return Statement(tree, locaPath, locaKey) + Separator + "c" + choiceIndex.ToString(CultureInfo.InvariantCulture);
        }

        public static string WithVariant(string lineId, string? variant)
        {
            if (string.IsNullOrEmpty(variant)) return lineId;
            RequireClean(variant, nameof(variant));
            return lineId + VariantSeparator + variant;
        }

        public static string AudioFileName(string fullId)
        {
            using var sha1 = SHA1.Create();
            byte[] hash = sha1.ComputeHash(Encoding.UTF8.GetBytes(fullId));
            var sb = new StringBuilder(16 + 4);
            for (int i = 0; i < 8; i++) sb.Append(hash[i].ToString("x2", CultureInfo.InvariantCulture));
            return sb.Append(".ogg").ToString();
        }

        private static void RequireClean(string? value, string name)
        {
            if (string.IsNullOrEmpty(value))
                throw new ArgumentException($"'{name}' darf nicht leer sein", name);
            if (value.IndexOf(Separator) >= 0 || value.IndexOf(VariantSeparator) >= 0)
                throw new ArgumentException($"'{name}' darf weder '{Separator}' noch '{VariantSeparator}' enthalten: {value}", name);
        }
    }
}
