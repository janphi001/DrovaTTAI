using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class TrackedIdsTests
    {
        [Fact]
        public void AnIdThatLeftWhileAnotherArrivedIsMissing()
        {
            var seen = new HashSet<int> { 2, 3 };
            Assert.Equal(new[] { 1 }, TrackedIds.Missing(new[] { 1, 2 }, seen));
        }

        [Fact]
        public void ASmallerMapStillDropsTheIdThatLeft()
        {
            var seen = new HashSet<int> { 2, 3, 4 };
            Assert.Equal(new[] { 1 }, TrackedIds.Missing(new[] { 1, 2 }, seen));
        }

        [Fact]
        public void PresentIdsStay()
        {
            var seen = new HashSet<int> { 1, 2 };
            Assert.Empty(TrackedIds.Missing(new[] { 1, 2 }, seen));
            Assert.Empty(TrackedIds.Missing(System.Array.Empty<int>(), seen));
        }
    }
}
