using Xunit;
using DrovaVoice.Core;

namespace DrovaVoice.Core.Tests
{
    public class BarkAttenuationTests
    {
        [Theory]
        [InlineData(0f, 1f)] [InlineData(3f, 1f)] [InlineData(16.5f, 0.5f)] [InlineData(30f, 0f)] [InlineData(100f, 0f)]
        public void FadesLinearlyBetweenMinAndMax(float distance, float expected) =>
            Assert.Equal(expected, BarkAttenuation.Gain(distance, 3f, 30f), 3);

        [Fact]
        public void GetsLouderAgainWhenTheDistanceShrinks()
        {
            float far = BarkAttenuation.Gain(25f, 3f, 30f);
            float near = BarkAttenuation.Gain(5f, 3f, 30f);
            Assert.True(near > far);
        }

        [Theory]
        [InlineData(-5f)] [InlineData(float.NaN)]
        public void InvalidDistanceStaysAudible(float distance) =>
            Assert.Equal(1f, BarkAttenuation.Gain(distance, 3f, 30f));

        [Fact]
        public void EqualMinAndMaxIsAStep()
        {
            Assert.Equal(1f, BarkAttenuation.Gain(10f, 10f, 10f));
            Assert.Equal(0f, BarkAttenuation.Gain(10.1f, 10f, 10f));
        }

        [Fact]
        public void NonFiniteRangeStaysAudibleAndInsideZeroToOne()
        {
            Assert.Equal(1f, BarkAttenuation.Gain(40f, float.NaN, 120f));
            Assert.Equal(1f, BarkAttenuation.Gain(40f, 15f, float.NaN));
            Assert.Equal(1f, BarkAttenuation.Gain(40f, float.PositiveInfinity, 120f));
            Assert.Equal(0f, BarkAttenuation.Gain(float.PositiveInfinity, 15f, 120f));
            float gain = BarkAttenuation.Gain(20f, 15f, 120f);
            Assert.InRange(gain, 0f, 1f);
        }
    }
}
