using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class TextPaceTests
    {
        [Fact]
        public void StartsEmptyAndEndsWithTheClip()
        {
            Assert.Equal(0, TextPace.Visible(100, 0f, 4f));
            Assert.Equal(100, TextPace.Visible(100, 4f, 4f));
            Assert.Equal(100, TextPace.Visible(100, 9f, 4f));
        }

        [Fact]
        public void GrowsInProportionToTheElapsedTime()
        {
            Assert.Equal(25, TextPace.Visible(100, 1f, 4f));
            Assert.Equal(50, TextPace.Visible(100, 2f, 4f));
            Assert.Equal(1, TextPace.Visible(100, 0.01f, 4f));
        }

        [Fact]
        public void WithoutAClipLengthShowsEverything()
        {
            Assert.Equal(40, TextPace.Visible(40, 1f, 0f));
            Assert.Equal(0, TextPace.Visible(0, 1f, 4f));
        }
    }
}
