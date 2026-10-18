using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class StatementGateTests
    {
        [Fact]
        public void TheClearRunsBeforeAFirstPriorityApiPrefix() =>
            Assert.True(StatementGate.BeforeApiPrefix > 800);

        [Theory]
        [InlineData(true)]
        [InlineData(false)]
        public void OnlyAnAttachedClipNeedsClearing(bool hasClip) =>
            Assert.Equal(hasClip, StatementGate.ClearAttachedClip(hasClip));

        [Fact]
        public void TheSecondSpeakerInTheSameFrameGetsTheirOwnClip()
        {
            string? clip = null;
            Speak(ref clip, "speaker-a");
            Speak(ref clip, "speaker-b");
            Assert.Equal("speaker-b", clip);
        }

        [Fact]
        public void ASpeakerWithoutAClipDoesNotKeepThePreviousOne()
        {
            string? clip = null;
            Speak(ref clip, "speaker-a");
            Speak(ref clip, null);
            Assert.Null(clip);
        }

        private static void Speak(ref string? clip, string? voice)
        {
            if (StatementGate.ClearAttachedClip(clip != null)) clip = null;
            if (clip != null) return;
            clip = voice;
        }
    }
}
