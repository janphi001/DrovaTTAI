using System;
using System.Collections.Generic;
using System.Text.Json;

namespace DrovaVoice.Core
{
    public static class CatalogReader
    {
        public static IReadOnlyList<string> TreeAddresses(string catalogJson)
        {
            var result = new List<string>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            using var doc = JsonDocument.Parse(catalogJson);
            if (!doc.RootElement.TryGetProperty("m_InternalIds", out var ids) || ids.ValueKind != JsonValueKind.Array) return result;
            foreach (var item in ids.EnumerateArray())
            {
                var path = item.ValueKind == JsonValueKind.String ? item.GetString() : null;
                if (path == null || !path.EndsWith(".asset", StringComparison.Ordinal)) continue;
                if (path.StartsWith("Assets/Editor/", StringComparison.Ordinal)) continue;
                int slash = path.LastIndexOf('/');
                if (!path.Substring(slash + 1).StartsWith("DT_", StringComparison.Ordinal)) continue;
                if (seen.Add(path)) result.Add(path);
            }
            return result;
        }
    }
}
