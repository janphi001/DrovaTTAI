using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class PcmBufferTests
    {
        [Fact]
        public void MonoMinuteFitsExactly()
        {
            Assert.Null(PcmBuffer.Reject(48000, 1, 48000, out int floats));
            Assert.Equal(48000, floats);
        }

        [Fact]
        public void StereoMinuteAtTheCapIsAccepted()
        {
            long samples = PcmBuffer.MaxFloats / 2;
            Assert.Null(PcmBuffer.Reject(samples, 2, 48000, out int floats));
            Assert.Equal(PcmBuffer.MaxFloats, floats);
        }

        [Fact]
        public void OneSampleOverTheCapIsRejected()
        {
            long samples = PcmBuffer.MaxFloats / 2 + 1;
            Assert.Equal("Datei zu lang", PcmBuffer.Reject(samples, 2, 48000, out int floats));
            Assert.Equal(0, floats);
        }

        [Fact]
        public void OverflowingHeaderIsRejectedInsteadOfBecomingATinyClip()
        {
            // 6148914691236517206 * 3 umbricht in einem long auf 2 und läge damit unter der Obergrenze.
            const long totalSamples = 6148914691236517206L;
            unchecked
            {
                long wrapped = totalSamples * 3;
                Assert.Equal(2L, wrapped);
                Assert.InRange(wrapped, 1L, PcmBuffer.MaxFloats);
            }
            Assert.Equal("Datei zu lang", PcmBuffer.Reject(totalSamples, 3, 48000, out int floats));
            Assert.Equal(0, floats);
        }

        [Theory]
        [InlineData(0, 1, 48000)]
        [InlineData(100, 0, 48000)]
        [InlineData(100, 9, 48000)]
        [InlineData(100, 1, 0)]
        [InlineData(-1, 1, 48000)]
        public void EmptyOrAbsurdHeadersAreRejected(long totalSamples, int channels, int sampleRate)
        {
            Assert.Equal("leere oder ungültige Datei", PcmBuffer.Reject(totalSamples, channels, sampleRate, out int floats));
            Assert.Equal(0, floats);
        }

        [Fact]
        public void AlignDropsAPartialFrame()
        {
            Assert.Equal(4, PcmBuffer.Align(5, 2));
            Assert.Equal(0, PcmBuffer.Align(1, 2));
            Assert.Equal(3, PcmBuffer.Align(3, 1));
            Assert.Equal(0, PcmBuffer.Align(4, 0));
        }
    }
}
