using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class IdleClipPolicyTests
    {
        [Fact]
        public void ReplacesTheFifteenFrameScanWithAFixedInterval()
        {
            Assert.Equal(0.25f, IdleClipPolicy.ScanIntervalSeconds);
            Assert.Equal(0.5f, IdleClipPolicy.IdleSeconds);
        }

        [Fact]
        public void PlayingSourceIsKeptAndTheIdleClockResets()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 0f, 0f));
            Assert.False(policy.ShouldStrip(1, true, 0.25f, 1f));
            Assert.False(policy.ShouldStrip(1, false, 0f, 1f));
            Assert.False(policy.ShouldStrip(1, false, 0f, 1f + IdleClipPolicy.IdleSeconds - 0.25f));
            Assert.True(policy.ShouldStrip(1, false, 0f, 1f + IdleClipPolicy.IdleSeconds));
        }

        [Fact]
        public void IdleSourceIsStrippedOnlyAfterTheTimeThreshold()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 0f, 10f));
            Assert.False(policy.ShouldStrip(1, false, 0f, 10f + IdleClipPolicy.IdleSeconds - 0.25f));
            Assert.True(policy.ShouldStrip(1, false, 0f, 10f + IdleClipPolicy.IdleSeconds));
        }

        [Fact]
        public void StrippingStartsANewIdlePeriod()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 0f, 0f));
            Assert.True(policy.ShouldStrip(1, false, 0f, IdleClipPolicy.IdleSeconds));
            Assert.False(policy.ShouldStrip(1, false, 0f, IdleClipPolicy.IdleSeconds));
            Assert.True(policy.ShouldStrip(1, false, 0f, IdleClipPolicy.IdleSeconds * 2f));
        }

        [Fact]
        public void PausedSourceIsNeverStripped()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 1.25f, 0f));
            Assert.False(policy.ShouldStrip(1, false, 1.25f, 30f));
            Assert.False(policy.ShouldStrip(1, false, 0.001f, 60f));
        }

        [Fact]
        public void PauseDoesNotCountTowardTheIdleTime()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 0f, 0f));
            Assert.False(policy.ShouldStrip(1, false, 0f, 0.25f));
            Assert.False(policy.ShouldStrip(1, false, 2f, 5f));
            Assert.False(policy.ShouldStrip(1, false, 0f, 5f));
            Assert.False(policy.ShouldStrip(1, false, 0f, 5f + IdleClipPolicy.IdleSeconds - 0.25f));
            Assert.True(policy.ShouldStrip(1, false, 0f, 5f + IdleClipPolicy.IdleSeconds));
        }

        [Fact]
        public void ZeroTimeIsNotAPause()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 0f, 0f));
            Assert.True(policy.ShouldStrip(1, false, 0f, IdleClipPolicy.IdleSeconds));
        }

        [Fact]
        public void SourcesAreTrackedIndependently()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(1, false, 0f, 0f));
            Assert.False(policy.ShouldStrip(2, false, 0f, 0.25f));
            Assert.True(policy.ShouldStrip(1, false, 0f, IdleClipPolicy.IdleSeconds));
            Assert.False(policy.ShouldStrip(2, false, 0f, IdleClipPolicy.IdleSeconds));
            Assert.True(policy.ShouldStrip(2, false, 0f, 0.25f + IdleClipPolicy.IdleSeconds));
        }

        [Fact]
        public void ForgetUnseenDropsTheIdleClock()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(7, false, 0f, 0f));
            policy.ForgetUnseen(new HashSet<int>());
            Assert.False(policy.ShouldStrip(7, false, 0f, 10f));
            Assert.True(policy.ShouldStrip(7, false, 0f, 10f + IdleClipPolicy.IdleSeconds));
        }

        [Fact]
        public void ForgetUnseenKeepsSourcesThatAreStillThere()
        {
            var policy = new IdleClipPolicy();
            Assert.False(policy.ShouldStrip(7, false, 0f, 0f));
            Assert.False(policy.ShouldStrip(8, false, 0f, 0f));
            policy.ForgetUnseen(new HashSet<int> { 7 });
            Assert.True(policy.ShouldStrip(7, false, 0f, IdleClipPolicy.IdleSeconds));
            Assert.False(policy.ShouldStrip(8, false, 0f, IdleClipPolicy.IdleSeconds));
        }
    }
}
