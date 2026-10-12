using System.Text.Json;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ManifestTests
    {
        private static Manifest Sample() => new Manifest
        {
            Language = "de",
            Lines =
            {
                new ManifestLine { Id = "DT_Main_NPC_Test|Dialog/NPC_Test|Plh_1", Tree = "DT_Main_NPC_Test", NodeId = 3, NodeType = "statement",
                    ActorName = "Testfrau", Category = "dialog", LocaPath = "Dialog/NPC_Test", LocaKey = "Plh_1", Text = "Schön, dass du da bist.",
                    Gvars = { "EVars_Player.Name" }, Next = { 4 }, Prev = { 2 } },
                new ManifestLine { Id = "DT_Main_NPC_Test|Dialog/NPC_Test|Plh_2|c1", Tree = "DT_Main_NPC_Test", NodeId = 4, NodeType = "choice",
                    ChoiceIndex = 1, ActorName = "Player", Category = "player", Generic = false, LocaPath = "Dialog/NPC_Test", LocaKey = "Plh_2", Text = "Ja." },
            },
        };

        [Fact]
        public void Serialized_json_uses_the_documented_field_names_and_raw_umlauts()
        {
            var json = ManifestJson.Serialize(Sample());
            Assert.Contains("\"locaPath\":\"Dialog/NPC_Test\"", json);
            Assert.Contains("\"nodeType\":\"statement\"", json);
            Assert.Contains("Schön", json);
            Assert.DoesNotContain("\\u00F6", json);
        }

        [Fact]
        public void A_missing_choice_index_is_omitted_but_a_present_one_is_written()
        {
            var json = ManifestJson.Serialize(Sample());
            Assert.Single(System.Text.RegularExpressions.Regex.Matches(json, "choiceIndex"));
            Assert.Contains("\"choiceIndex\":1", json);
        }

        [Fact]
        public void Roundtrip_keeps_every_field()
        {
            var back = ManifestJson.Deserialize(ManifestJson.Serialize(Sample()));
            Assert.Equal("de", back.Language);
            Assert.Equal(2, back.Lines.Count);
            var first = back.Lines[0];
            Assert.Equal("Schön, dass du da bist.", first.Text);
            Assert.Equal(new[] { "EVars_Player.Name" }, first.Gvars);
            Assert.Equal(new[] { 4 }, first.Next);
            Assert.Equal(new[] { 2 }, first.Prev);
            Assert.Null(first.ChoiceIndex);
            Assert.Equal(1, back.Lines[1].ChoiceIndex);
        }

        [Fact]
        public void Invalid_json_throws_a_json_exception()
            => Assert.ThrowsAny<JsonException>(() => ManifestJson.Deserialize("{ das ist kein json"));
    }
}
