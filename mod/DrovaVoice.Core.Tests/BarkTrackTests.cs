using System;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class BarkTrackTests
    {
        [Fact]
        public void SameInstanceStaysTracked() => Assert.True(BarkTrack.SameClip(17, 17));

        [Fact]
        public void ADifferentClipIsNotTheSame() => Assert.False(BarkTrack.SameClip(17, 18));

        [Fact]
        public void SteadyStateCompareAllocatesNothing()
        {
            long before = GC.GetAllocatedBytesForCurrentThread();
            bool same = false;
            for (int i = 0; i < 20000; i++)
                same |= BarkTrack.SameClip(i, i);
            long used = GC.GetAllocatedBytesForCurrentThread() - before;
            Assert.True(same);
            Assert.Equal(0, used);
        }
    }
}
