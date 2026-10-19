using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class StatementGateTests
    {
        private const string Mod = "DrovaVoice/";

        [Fact]
        public void TheClearRunsBeforeAFirstPriorityApiPrefix() =>
            Assert.True(StatementGate.BeforeApiPrefix > 800);

        [Theory]
        [InlineData("DrovaVoice/bark/hallo.ogg", true)]
        [InlineData("DrovaVoice/dialog/zeile.ogg", true)]
        [InlineData("DrovaTTS/zeile.wav", false)]
        [InlineData(null, false)]
        public void OnlyClipsOfThisModAreCleared(string? clip, bool cleared) =>
            Assert.Equal(cleared, StatementGate.ClearAttachedClip(clip, Mod));

        [Fact]
        public void TheSecondSpeakerOfASharedStatementGetsTheirOwnClip()
        {
            string? clip = null;
            Speak(ref clip, Mod + "bark/a.ogg");
            Speak(ref clip, Mod + "bark/b.ogg");
            Assert.Equal(Mod + "bark/b.ogg", clip);
        }

        [Fact]
        public void AForeignClipStaysAttached()
        {
            string? clip = "DrovaTTS/zeile.wav";
            Speak(ref clip, Mod + "dialog/zeile.ogg");
            Assert.Equal("DrovaTTS/zeile.wav", clip);
        }

        private static void Speak(ref string? clip, string? voice)
        {
            if (StatementGate.ClearAttachedClip(clip, Mod)) clip = null;
            if (clip != null) return;
            clip = voice;
        }
    }
}
