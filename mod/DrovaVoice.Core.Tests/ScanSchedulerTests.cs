using System;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ScanSchedulerTests
    {
        [Fact]
        public void FirstLookIsDueAndDoesNotConsumeTheSlot()
        {
            var scheduler = new ScanScheduler(0.25);
            Assert.True(scheduler.IsDue(0));
            Assert.True(scheduler.IsDue(0));
        }

        [Fact]
        public void MarkRanHoldsOffEveryCallerUntilTheIntervalElapses()
        {
            var scheduler = new ScanScheduler(0.25);
            scheduler.MarkRan(1.0);
            Assert.False(scheduler.IsDue(1.0));
            Assert.False(scheduler.IsDue(1.24));
            Assert.True(scheduler.IsDue(1.25));
        }

        [Fact]
        public void ASecondMarkStartsANewInterval()
        {
            var scheduler = new ScanScheduler(0.25);
            scheduler.MarkRan(1.0);
            scheduler.MarkRan(1.25);
            Assert.False(scheduler.IsDue(1.49));
            Assert.True(scheduler.IsDue(1.5));
        }

        [Fact]
        public void AClockStepBackwardsIsDue()
        {
            var scheduler = new ScanScheduler(0.25);
            scheduler.MarkRan(10);
            Assert.True(scheduler.IsDue(9.9));
        }

        [Theory]
        [InlineData(0)]
        [InlineData(-0.1)]
        public void RejectsANonPositiveInterval(double interval) =>
            Assert.Throws<ArgumentOutOfRangeException>(() => new ScanScheduler(interval));

        [Fact]
        public void RejectsANonFiniteInterval()
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => new ScanScheduler(double.PositiveInfinity));
            Assert.Throws<ArgumentOutOfRangeException>(() => new ScanScheduler(double.NaN));
        }

        [Fact]
        public void ExposesTheInterval() => Assert.Equal(0.25, new ScanScheduler(0.25).IntervalSeconds);
    }
}
