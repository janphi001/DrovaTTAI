using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class RuntimeLineLogTests
    {
        private static ManifestLine Line(string id) => new ManifestLine
        {
            Id = id, Tree = "DT_Test_Template", ActorName = "Testfigur", LocaPath = "Dialog/Test", LocaKey = "Plh_1", Text = "Erfundener Satz.",
        };

        [Fact]
        public void WritesANewLineOnceAsSingleLineJson()
        {
            var log = new RuntimeLineLog(new string[0]);
            string? json = log.Add(Line("DT_Test_Template|Dialog/Test|Plh_1"));
            Assert.NotNull(json);
            Assert.DoesNotContain("\n", json);
            Assert.Contains("\"locaKey\":\"Plh_1\"", json);
            Assert.Null(log.Add(Line("DT_Test_Template|Dialog/Test|Plh_1")));
            Assert.Equal(1, log.Count);
        }

        [Fact]
        public void KnowsTheIdsOfTheExistingFile()
        {
            var first = new RuntimeLineLog(new string[0]);
            string json = first.Add(Line("DT_Test_Template|Dialog/Test|Plh_1"))!;
            var second = new RuntimeLineLog(new[] { json, "", "{kaputt" });
            Assert.True(second.Contains("DT_Test_Template|Dialog/Test|Plh_1"));
            Assert.Null(second.Add(Line("DT_Test_Template|Dialog/Test|Plh_1")));
            Assert.NotNull(second.Add(Line("DT_Test_Template|Dialog/Test|Plh_2")));
        }

        [Fact]
        public void RoundTripsTheFields()
        {
            var log = new RuntimeLineLog(new string[0]);
            var back = ManifestJson.DeserializeLine(log.Add(Line("DT_Test_Template|Dialog/Test|Plh_1"))!)!;
            Assert.Equal("Testfigur", back.ActorName);
            Assert.Equal("Erfundener Satz.", back.Text);
            Assert.Equal("statement", back.NodeType);
        }
    }
}
