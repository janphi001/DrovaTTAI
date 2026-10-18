using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class AssetLeaseTests
    {
        [Fact]
        public void AVariantSwitchReleasesTheFirstBatchAndKeepsTheNext()
        {
            var lease = new AssetLease();
            Assert.True(lease.Keep());
            Assert.True(lease.Keep());
            Assert.Equal(2, lease.Discard());
            Assert.Equal(0, lease.Kept);
            Assert.False(lease.Closed);
            Assert.True(lease.Keep());
            Assert.Equal(1, lease.End());
            Assert.True(lease.Closed);
            Assert.False(lease.Keep());
            Assert.Equal(0, lease.Kept);
            Assert.Equal(0, lease.End());
        }

        [Fact]
        public void DiscardOnAnEmptyLeaseStaysOpen()
        {
            var lease = new AssetLease();
            Assert.Equal(0, lease.Discard());
            Assert.True(lease.Keep());
            Assert.Equal(1, lease.Kept);
        }
    }
}
