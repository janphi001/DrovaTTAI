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
        [InlineData("bark/x.ogg", VoiceCategory.Dialog)]
        public void CategoryComesFromFolder(string file, VoiceCategory expected) =>
            Assert.Equal(expected, AudioIndex.CategoryOf(file));
    }
}
