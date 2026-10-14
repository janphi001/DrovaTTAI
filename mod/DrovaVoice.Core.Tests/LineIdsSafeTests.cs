using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class LineIdsSafeTests
    {
        [Fact]
        public void TryStatementMatchesStatement()
        {
            Assert.True(LineIds.TryStatement("DT_X", "Dialog\\A/", "Plh_1", out string id));
            Assert.Equal(LineIds.Statement("DT_X", "Dialog\\A/", "Plh_1"), id);
        }

        [Theory]
        [InlineData(null, "Dialog/A", "Plh_1")]
        [InlineData("DT_X", null, "Plh_1")]
        [InlineData("DT_X", "Dialog/A", null)]
        [InlineData("", "Dialog/A", "Plh_1")]
        [InlineData("DT_X", "/", "Plh_1")]
        [InlineData("DT_X", "Dialog/A", "")]
        [InlineData("DT|X", "Dialog/A", "Plh_1")]
        public void TryStatementReturnsFalseInsteadOfThrowing(string? tree, string? path, string? key)
        {
            Assert.False(LineIds.TryStatement(tree, path, key, out string id));
            Assert.Equal("", id);
        }

        [Fact]
        public void TryChoiceMatchesChoice()
        {
            Assert.True(LineIds.TryChoice("DT_X", "Dialog/A", "Plh_2", 3, out string id));
            Assert.Equal(LineIds.Choice("DT_X", "Dialog/A", "Plh_2", 3), id);
        }

        [Fact]
        public void TryChoiceRejectsNegativeIndexAndBadParts()
        {
            Assert.False(LineIds.TryChoice("DT_X", "Dialog/A", "Plh_2", -1, out _));
            Assert.False(LineIds.TryChoice("DT_X", "Dialog/A", null, 0, out _));
        }

        [Theory]
        [InlineData(true, "Global/G", "Dialog/T", "Global/G")]
        [InlineData(false, "Global/G", "Dialog/T", "Dialog/T")]
        [InlineData(true, null, "Dialog/T", "")]
        [InlineData(false, "Global/G", null, "")]
        public void ResolveLocaPathFollowsUseGlobalLoca(bool useGlobal, string? global, string? tree, string expected) =>
            Assert.Equal(expected, LineIds.ResolveLocaPath(useGlobal, global, tree));
    }
}
