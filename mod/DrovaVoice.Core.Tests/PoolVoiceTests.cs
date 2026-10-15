using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class PoolVoiceTests
    {
        private static readonly string[] All = { "vm1", "vm2", "vm3", "vw1", "vw2", "vw3" };

        [Theory]
        [InlineData("", 0x811C9DC5u)]
        [InlineData("a", 0xE40C292Cu)]
        [InlineData("foobar", 0xBF9CF968u)]
        public void Fnv1aMatchesTheReferenceVectors(string text, uint expected) =>
            Assert.Equal(expected, PoolVoice.Fnv1a(text));

        [Theory]
        [InlineData("vm1", true)] [InlineData("vw12", true)] [InlineData("neutral", false)]
        [InlineData("vx1", false)] [InlineData("vm", false)] [InlineData("", false)] [InlineData(null, false)]
        public void RecognisesPoolTags(string? tag, bool expected) => Assert.Equal(expected, PoolVoice.IsPoolTag(tag));

        [Fact]
        public void SameFigureAlwaysGetsTheSameVoice()
        {
            string first = PoolVoice.Pick(All, 'm', "guid-1", "Line|A|1")!;
            for (int i = 0; i < 20; i++)
                Assert.Equal(first, PoolVoice.Pick(All, 'm', "guid-1", "Line|A|" + i));
        }

        [Fact]
        public void FigureKeyBeatsTheLineId() =>
            Assert.Equal(PoolVoice.Pick(All, 'w', "guid-9", "X"), PoolVoice.Pick(All, 'w', "guid-9", "Y"));

        [Fact]
        public void GenderFiltersTheCandidates()
        {
            for (int i = 0; i < 50; i++)
            {
                Assert.StartsWith("vm", PoolVoice.Pick(All, 'm', "g" + i, "L")!);
                Assert.StartsWith("vw", PoolVoice.Pick(All, 'w', "g" + i, "L")!);
            }
        }

        [Fact]
        public void WithoutFigureKeyTheLineIdDecidesAndAllTagsAreCandidates()
        {
            Assert.Equal(PoolVoice.Pick(All, null, null, "L1"), PoolVoice.Pick(All, null, "", "L1"));
            var seen = new HashSet<string>();
            for (int i = 0; i < 200; i++) seen.Add(PoolVoice.Pick(All, null, null, "Line" + i)!);
            Assert.Equal(6, seen.Count);
        }

        [Fact]
        public void GenderWithoutMatchingTagsFallsBackToAllTags() =>
            Assert.StartsWith("vw", PoolVoice.Pick(new[] { "vw1", "vw2" }, 'm', "g", "L")!);

        [Fact]
        public void DifferentFiguresSpreadOverTheVoices()
        {
            var seen = new HashSet<string>();
            for (int i = 0; i < 100; i++) seen.Add(PoolVoice.Pick(All, 'm', "guid-" + i, "L")!);
            Assert.Equal(3, seen.Count);
        }

        [Fact]
        public void IgnoresNonPoolTagsAndEmptyLists()
        {
            Assert.Null(PoolVoice.Pick(new string[0], 'm', "g", "L"));
            Assert.Null(PoolVoice.Pick(new[] { "neutral" }, null, "g", "L"));
            Assert.Equal("vm1", PoolVoice.Pick(new[] { "neutral", "vm1" }, null, "g", "L"));
        }

        [Theory]
        [InlineData("Strong", 'm')] [InlineData("Petite", 'w')] [InlineData("None", null)] [InlineData(null, null)] [InlineData("", null)]
        public void MapsBodyTypeToGender(string? body, char? expected) => Assert.Equal(expected, PoolVoice.GenderFromBodyType(body));

        [Fact]
        public void ResolveReturnsTheBaseIdWhenItHasAnEntryAndOtherwiseThePoolVariant()
        {
            const string json = @"{""version"":1,""language"":""de"",""entries"":{
              ""DT_A|P|1"": {""file"": ""bark/aaaaaaaaaaaaaaaa.ogg"", ""duration"": 1.0},
              ""DT_G|P|1#vm1"": {""file"": ""bark/bbbbbbbbbbbbbbbb.ogg"", ""duration"": 1.0},
              ""DT_G|P|1#vm2"": {""file"": ""bark/cccccccccccccccc.ogg"", ""duration"": 1.0}}}";
            var index = AudioIndex.Parse(json, "de");
            Assert.Equal("DT_A|P|1", PoolVoice.Resolve(index, "DT_A|P|1", new FigureInfo('m', "g")));
            string a = PoolVoice.Resolve(index, "DT_G|P|1", new FigureInfo('m', "g"))!;
            Assert.StartsWith("DT_G|P|1#vm", a);
            Assert.Equal(a, PoolVoice.Resolve(index, "DT_G|P|1", new FigureInfo('m', "g")));
            Assert.Equal("DT_X|P|9", PoolVoice.Resolve(index, "DT_X|P|9", null));
            Assert.StartsWith("DT_G|P|1#vm", PoolVoice.Resolve(index, "DT_G|P|1", null)!);
            Assert.Null(PoolVoice.Resolve(index, null, null));
        }
    }
}
