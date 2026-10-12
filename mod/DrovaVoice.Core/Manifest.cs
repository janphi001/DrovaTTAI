using System.Collections.Generic;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DrovaVoice.Core
{
    public sealed class ManifestLine
    {
        public string Id { get; set; } = "";
        public string Tree { get; set; } = "";
        public int NodeId { get; set; }
        public string NodeType { get; set; } = "statement";
        public int? ChoiceIndex { get; set; }
        public string ActorName { get; set; } = "";
        public string Category { get; set; } = "dialog";
        public bool Generic { get; set; }
        public string LocaPath { get; set; } = "";
        public string LocaKey { get; set; } = "";
        public string Text { get; set; } = "";
        public List<string> Gvars { get; set; } = new List<string>();
        public List<int> Next { get; set; } = new List<int>();
        public List<int> Prev { get; set; } = new List<int>();
    }

    public sealed class Manifest
    {
        public int Version { get; set; } = 1;
        public string Language { get; set; } = "de";
        public List<ManifestLine> Lines { get; set; } = new List<ManifestLine>();
    }

    public static class ManifestJson
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            WriteIndented = false,
        };

        public static string Serialize(Manifest manifest) => JsonSerializer.Serialize(manifest, Options);

        public static Manifest Deserialize(string json)
            => JsonSerializer.Deserialize<Manifest>(json, Options) ?? throw new JsonException("Manifest ist leer");
    }
}
