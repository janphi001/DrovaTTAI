using System;
using System.Linq;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ClipBudgetTests
    {
        [Fact]
        public void NothingEvictedWithinBudget()
        {
            var b = new ClipBudget(100, 1);
            Assert.Empty(b.Add("a", 40));
            Assert.Empty(b.Add("b", 40));
            Assert.Equal(80, b.TotalBytes);
            Assert.Equal(2, b.Count);
        }

        [Fact]
        public void EvictsLeastRecentlyUsedFirst()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 40); b.Add("b", 40);
            var evicted = b.Add("c", 40);
            Assert.Equal(new[] { "a" }, evicted);
            Assert.False(b.Contains("a"));
            Assert.True(b.Contains("b") && b.Contains("c"));
            Assert.Equal(80, b.TotalBytes);
        }

        [Fact]
        public void TouchRefreshesRecency()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 40); b.Add("b", 40);
            b.Touch("a");
            Assert.Equal(new[] { "b" }, b.Add("c", 40));
        }

        [Fact]
        public void NewestEntriesAreNeverEvictedEvenOverBudget()
        {
            var b = new ClipBudget(50, 2);
            b.Add("a", 40); b.Add("b", 40);
            Assert.Equal(new[] { "a" }, b.Add("x", 0));   // nur 2 geschützt: a ist drittjüngster und wird verdrängt
            Assert.False(b.Contains("a"));
            Assert.True(b.Contains("b") && b.Contains("x"));
            Assert.Equal(40, b.TotalBytes);
        }

        [Fact]
        public void ProtectedEntriesStayWhenTheyAloneExceedTheBudget()
        {
            var b = new ClipBudget(10, 3);
            b.Add("a", 100); b.Add("b", 100); b.Add("c", 100);
            Assert.Equal(3, b.Count);
            Assert.Equal(300, b.TotalBytes);
        }

        [Fact]
        public void ReAddingUpdatesBytesAndRecency()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 30); b.Add("b", 30);
            Assert.Empty(b.Add("a", 50));
            Assert.Equal(80, b.TotalBytes);
            Assert.Equal(new[] { "b" }, b.Add("c", 30));
        }

        [Fact]
        public void RemoveFreesBytesAndIgnoresUnknownKeys()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 40);
            b.Remove("a");
            b.Remove("nope");
            Assert.Equal(0, b.TotalBytes);
            Assert.Equal(0, b.Count);
            Assert.False(b.Contains("a"));
        }

        [Fact]
        public void TouchOfUnknownKeyIsNoop()
        {
            var b = new ClipBudget(100, 1);
            b.Touch("nope");
            Assert.Equal(0, b.Count);
        }

        [Fact]
        public void RejectsNegativeBytes() =>
            Assert.Throws<ArgumentOutOfRangeException>(() => new ClipBudget(100, 1).Add("a", -1));

        [Fact]
        public void EvictsSeveralToFit()
        {
            var b = new ClipBudget(100, 1);
            b.Add("a", 30); b.Add("b", 30); b.Add("c", 30);
            var evicted = b.Add("d", 90);
            Assert.Equal(new[] { "a", "b", "c" }, evicted.ToArray());
            Assert.Equal(90, b.TotalBytes);
        }
    }
}
