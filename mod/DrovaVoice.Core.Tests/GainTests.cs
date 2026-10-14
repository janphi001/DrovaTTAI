using System;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class GainTests
    {
        [Fact]
        public void HundredPercentIsExactIdentity()
        {
            var samples = new[] { 0.9f, -0.95f, 0.123456f, 0f };
            var copy = (float[])samples.Clone();
            Gain.Apply(samples, 100);
            Assert.Equal(copy, samples);
        }

        [Fact]
        public void ZeroPercentIsSilence()
        {
            var samples = new[] { 0.5f, -0.9f };
            Gain.Apply(samples, 0);
            Assert.All(samples, s => Assert.Equal(0f, s));
        }

        [Fact]
        public void BelowHundredScalesLinearly()
        {
            var samples = new[] { 0.8f, -0.4f };
            Gain.Apply(samples, 50);
            Assert.Equal(0.4f, samples[0], 5);
            Assert.Equal(-0.2f, samples[1], 5);
        }

        [Fact]
        public void BoostBelowKneeIsLinear()
        {
            var samples = new[] { 0.3f, -0.3f };
            Gain.Apply(samples, 200);
            Assert.Equal(0.6f, samples[0], 5);
            Assert.Equal(-0.6f, samples[1], 5);
        }

        [Fact]
        public void BoostAboveKneeIsLimitedBelowOne()
        {
            var samples = new[] { 0.9f, -0.9f };
            Gain.Apply(samples, 200); // 1.8 vor dem Begrenzer
            Assert.InRange(samples[0], 0.8f, 1.0f);
            Assert.InRange(samples[1], -1.0f, -0.8f);
            Assert.Equal(-samples[0], samples[1], 6);
        }

        [Fact]
        public void BoostNeverExceedsFullScale()
        {
            var samples = new[] { 1f, -1f, 10f, -1000f, float.MaxValue / 4, 0.99f };
            Gain.Apply(samples, 200);
            Assert.All(samples, s => Assert.InRange(s, -1.0f, 1.0f));
        }

        [Fact]
        public void LimiterIsMonotonicAndContinuousAtKnee()
        {
            float prev = float.MinValue;
            for (float y = 0f; y <= 4f; y += 0.01f)
            {
                float o = Gain.Limit(y);
                Assert.True(o >= prev - 1e-6f, $"nicht monoton bei {y}");
                prev = o;
            }
            Assert.Equal(0.8f, Gain.Limit(0.8f), 6);
            Assert.Equal(0.8f, Gain.Limit(0.8001f), 3);
        }

        [Fact]
        public void LimiterMapsNaNToZero() =>
            Assert.Equal(0f, Gain.Limit(float.NaN));

        [Theory]
        [InlineData(-5, 0)]
        [InlineData(0, 0)]
        [InlineData(100, 100)]
        [InlineData(200, 200)]
        [InlineData(250, 200)]
        public void ClampsPercent(int input, int expected) =>
            Assert.Equal(expected, Gain.ClampPercent(input));

        [Fact]
        public void PercentOverMaxActsLikeMax()
        {
            var a = new[] { 0.5f, 0.9f };
            var b = (float[])a.Clone();
            Gain.Apply(a, 200);
            Gain.Apply(b, 999);
            Assert.Equal(a, b);
        }

        [Fact]
        public void EmptyArrayIsFine() => Gain.Apply(Array.Empty<float>(), 150);
    
        [Fact]
        public void LimiterIsSymmetricForNegativeValues()
        {
            for (float y = 0f; y <= 4f; y += 0.05f)
                Assert.Equal(-Gain.Limit(y), Gain.Limit(-y));
        }
    }
}
