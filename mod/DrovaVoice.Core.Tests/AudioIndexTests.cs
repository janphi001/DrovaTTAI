using System.IO;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class AudioIndexTests
    {
        private const string Good = @"{
  ""version"": 1, ""language"": ""de"",
  ""entries"": {
    ""DT_X|Dialog/A|Plh_1"":    {""file"": ""dialog/0123456789abcdef.ogg"", ""duration"": 3.214},
    ""DT_X|Dialog/A|Plh_2|c0"": {""file"": ""player/fedcba9876543210.ogg"", ""duration"": 1.9}
  },
  ""variants"": {}
}";

        [Fact]
        public void ParsesEntriesAndCategories()
        {
            var index = AudioIndex.Parse(Good, "de");
            Assert.Equal(2, index.Count);
            Assert.Equal(0, index.Skipped);
            Assert.True(index.TryGet("DT_X|Dialog/A|Plh_1", out var a));
            Assert.Equal("dialog/0123456789abcdef.ogg", a.File);
            Assert.Equal(3.214, a.Duration, 3);
            Assert.Equal(VoiceCategory.Dialog, a.Category);
            Assert.True(index.TryGet("DT_X|Dialog/A|Plh_2|c0", out var b));
            Assert.Equal(VoiceCategory.Player, b.Category);
        }

        [Fact]
        public void BarkFolderGetsTheBarkCategory()
        {
            const string json = @"{""version"":1,""language"":""de"",""entries"":{
              ""DT_W|Dialog/W|Plh_1"": {""file"": ""bark/0123456789abcdef.ogg"", ""duration"": 1.0}}}";
            var index = AudioIndex.Parse(json, "de");
            Assert.True(index.TryGet("DT_W|Dialog/W|Plh_1", out var e));
            Assert.Equal(VoiceCategory.Bark, e.Category);
        }

        [Fact]
        public void UnknownEmptyAndNullIdsAreMisses()
        {
            var index = AudioIndex.Parse(Good, "de");
            Assert.False(index.TryGet("DT_X|Dialog/A|Plh_9", out _));
            Assert.False(index.TryGet("", out _));
            Assert.False(index.TryGet(null, out _));
        }

        [Fact]
        public void LanguageIsComparedIgnoringCase() =>
            Assert.Equal(2, AudioIndex.Parse(Good, "DE").Count);

        [Fact]
        public void RejectsWrongLanguage() =>
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(Good, "en"));

        [Fact]
        public void RejectsWrongVersion() =>
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(Good.Replace("\"version\": 1", "\"version\": 2"), "de"));

        [Fact]
        public void RejectsMissingVersionOrEntries()
        {
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(@"{""language"":""de"",""entries"":{}}", "de"));
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(@"{""version"":1,""language"":""de""}", "de"));
        }

        [Theory]
        [InlineData("")]
        [InlineData("not json")]
        [InlineData("[]")]
        [InlineData("null")]
        public void RejectsInvalidJson(string json) =>
            Assert.Throws<IndexFormatException>(() => AudioIndex.Parse(json, "de"));

        [Theory]
        [InlineData("../x.ogg")]
        [InlineData("dialog/../../x.ogg")]
        [InlineData("/abs.ogg")]
        [InlineData("C:/x.ogg")]
        [InlineData("a\\b.ogg")]
        [InlineData("")]
        public void SkipsUnsafePaths(string file)
        {
            string json = @"{""version"":1,""language"":""de"",""entries"":{""DT_X|A|K"":{""file"":""" + file.Replace("\\", "\\\\") + @""",""duration"":1}}}";
            var index = AudioIndex.Parse(json, "de");
            Assert.Equal(0, index.Count);
            Assert.Equal(1, index.Skipped);
        }

        [Fact]
        public void SkipsEntriesWithoutFileOrOfWrongShape()
        {
            string json = @"{""version"":1,""language"":""de"",""entries"":{
              ""A|B|1"": {""duration"": 1},
              ""A|B|2"": ""text"",
              ""A|B|3"": {""file"": 5, ""duration"": 1},
              ""A|B|4"": {""file"": ""dialog/ok.ogg""}
            }}";
            var index = AudioIndex.Parse(json, "de");
            Assert.Equal(1, index.Count);
            Assert.Equal(3, index.Skipped);
            Assert.True(index.TryGet("A|B|4", out var e));
            Assert.Equal(0.0, e.Duration);
        }

        [Fact]
        public void ResolvePathStaysInsideRoot()
        {
            string root = Path.Combine(Path.GetTempPath(), "audio-root");
            Assert.Equal(Path.Combine(root, "dialog", "a.ogg"), AudioIndex.ResolvePath(root, "dialog/a.ogg"));
            Assert.Null(AudioIndex.ResolvePath(root, "../a.ogg"));
        }

        [Theory]
        [InlineData("player/default/x.ogg", VoiceCategory.Player)]
        [InlineData("dialog/x.ogg", VoiceCategory.Dialog)]
        [InlineData("bark/x.ogg", VoiceCategory.Bark)]
        public void CategoryComesFromFolder(string file, VoiceCategory expected) =>
            Assert.Equal(expected, AudioIndex.CategoryOf(file));
    
        private const string Choices = @"{
  ""version"": 1, ""language"": ""de"",
  ""entries"": {
    ""DT_X|Dialog/A|Q1|c2"": {""file"": ""player/a.ogg"", ""duration"": 1},
    ""DT_X|Dialog/A|Q2|c0"": {""file"": ""player/b.ogg"", ""duration"": 1},
    ""DT_X|Dialog/A|Q2|c1"": {""file"": ""player/c.ogg"", ""duration"": 1},
    ""DT_X|Dialog/A|Q3|c0#neutral"": {""file"": ""player/d.ogg"", ""duration"": 1},
    ""DT_X|Dialog/A|S1"": {""file"": ""dialog/e.ogg"", ""duration"": 1}
  }
}";

        [Fact]
        public void UniqueChoiceByKeyFindsTheOnlyChoiceEntry()
        {
            var index = AudioIndex.Parse(Choices, "de");
            Assert.True(index.TryGetUniqueChoice("DT_X|Dialog/A|Q1", out string id, out var entry));
            Assert.Equal("DT_X|Dialog/A|Q1|c2", id);
            Assert.Equal("player/a.ogg", entry.File);
        }

        [Fact]
        public void UniqueChoiceByKeyIsRefusedWhenAmbiguous()
        {
            var index = AudioIndex.Parse(Choices, "de");
            Assert.False(index.TryGetUniqueChoice("DT_X|Dialog/A|Q2", out string id, out _));
            Assert.Equal("", id);
        }

        [Theory]
        [InlineData("DT_X|Dialog/A|S1")]      // Aussage, keine Auswahl
        [InlineData("DT_X|Dialog/A|Q3")]      // nur Variante vorhanden
        [InlineData("DT_X|Dialog/A|nope")]
        [InlineData("")]
        public void UniqueChoiceByKeyMissesOtherKeys(string baseId)
        {
            var index = AudioIndex.Parse(Choices, "de");
            Assert.False(index.TryGetUniqueChoice(baseId, out _, out _));
        }

        private const string WithNeutral = @"{
  ""version"": 1, ""language"": ""de"",
  ""entries"": {
    ""DT_X|Dialog/A|Plh_1#neutral"": {""file"": ""dialog/0123456789abcdef.ogg"", ""duration"": 1.0},
    ""DT_X|Dialog/A|Plh_2"":         {""file"": ""dialog/fedcba9876543210.ogg"", ""duration"": 2.0},
    ""DT_X|Dialog/A|Plh_1|c0#neutral"": {""file"": ""dialog/aaaaaaaaaaaaaaaa.ogg"", ""duration"": 1.5},
    ""DT_X|Dialog/A|Plh_3#neutral|c0"": {""file"": ""dialog/bbbbbbbbbbbbbbbb.ogg"", ""duration"": 1.5}
  },
  ""variants"": {""DT_X|Dialog/A|Plh_1"": [""neutral""]}
}";

        [Fact]
        public void ResolveVariantPrefersTheVariantEntry()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.Equal("DT_X|Dialog/A|Plh_1#neutral", index.ResolveVariant("DT_X|Dialog/A|Plh_1", LineIds.NeutralVariant));
        }

        [Fact]
        public void ResolveVariantKeepsTheBaseIdWithoutVariantEntry()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.Equal("DT_X|Dialog/A|Plh_2", index.ResolveVariant("DT_X|Dialog/A|Plh_2", LineIds.NeutralVariant));
            Assert.Equal("DT_X|Dialog/A|Plh_9", index.ResolveVariant("DT_X|Dialog/A|Plh_9", LineIds.NeutralVariant));
            Assert.Equal("DT_X|Dialog/A|Plh_2|c0", index.ResolveVariant("DT_X|Dialog/A|Plh_2|c0", LineIds.NeutralVariant));
        }

        [Fact]
        public void ResolveVariantPassesNullAndEmptyThrough()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            Assert.Null(index.ResolveVariant(null, LineIds.NeutralVariant));
            Assert.Equal("", index.ResolveVariant("", LineIds.NeutralVariant));
        }

        [Fact]
        public void VariantEntriesAreNotCountedAsChoiceFallbacks()
        {
            var index = AudioIndex.Parse(WithNeutral, "de");
            // Variante hinter dem Auswahlsuffix: scheitert schon an der Ziffernprüfung.
            Assert.False(index.TryGetUniqueChoice("DT_X|Dialog/A|Plh_1", out _, out _));
            // Variante vor dem Auswahlsuffix: nur der Varianten-Skip hält sie aus der Suche.
            Assert.False(index.TryGetUniqueChoice("DT_X|Dialog/A|Plh_3#neutral", out _, out _));
        }
    }
}
