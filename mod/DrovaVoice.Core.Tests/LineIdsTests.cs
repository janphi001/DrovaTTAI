using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class LineIdsTests
    {
        public sealed record Vector(
            string kind, string tree, string locaPath, string locaKey,
            int? choiceIndex, string? variant, string expectedId, string expectedFile);

        public static IEnumerable<object[]> Vectors()
        {
            string path = Path.Combine(AppContext.BaseDirectory, "vectors", "line_ids.json");
            var vectors = JsonSerializer.Deserialize<List<Vector>>(File.ReadAllText(path))!;
            foreach (var v in vectors) yield return new object[] { v };
        }

        [Theory]
        [MemberData(nameof(Vectors))]
        public void BuildsExpectedIdAndFileName(Vector v)
        {
            string id = v.kind == "choice"
                ? LineIds.Choice(v.tree, v.locaPath, v.locaKey, v.choiceIndex!.Value)
                : LineIds.Statement(v.tree, v.locaPath, v.locaKey);
            id = LineIds.WithVariant(id, v.variant);

            Assert.Equal(v.expectedId, id);
            Assert.Equal(v.expectedFile, LineIds.AudioFileName(id));
        }

        [Fact]
        public void RejectsSeparatorInParts() =>
            Assert.Throws<ArgumentException>(() => LineIds.Statement("DT|X", "Dialog/A", "Plh_1"));

        [Fact]
        public void RejectsNegativeChoiceIndex() =>
            Assert.Throws<ArgumentOutOfRangeException>(() => LineIds.Choice("DT_X", "Dialog/A", "Plh_1", -1));

        [Fact]
        public void EmptyVariantIsNoop() =>
            Assert.Equal("DT_X|A|Plh_1", LineIds.WithVariant("DT_X|A|Plh_1", ""));

        [Fact]
        public void RejectsEmptyTree() =>
            Assert.Throws<ArgumentException>(() => LineIds.Statement("", "Dialog/A", "Plh_1"));

        [Fact]
        public void RejectsEmptyLocaKey() =>
            Assert.Throws<ArgumentException>(() => LineIds.Choice("DT_X", "Dialog/A", "", 0));

        [Fact]
        public void RejectsEmptyLocaPathAfterNormalization() =>
            Assert.Throws<ArgumentException>(() => LineIds.Statement("DT_X", "/", "Plh_1"));
    }
}
