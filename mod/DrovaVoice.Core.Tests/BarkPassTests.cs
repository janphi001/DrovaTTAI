using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class BarkPassTests
    {
        private sealed class Item
        {
            public string Name = "";
            public bool ThrowOnRead;
            public bool Active;
            public float Distance;
            public bool ThrowOnScale;
            public bool ThrowOnDrop;
        }

        [Fact]
        public void AThrowingSourceIsDroppedAndTheOthersStillScale()
        {
            var items = new List<Item>
            {
                new Item { Name = "near", Active = true, Distance = 1f },
                new Item { Name = "bad", ThrowOnRead = true },
                new Item { Name = "far", Active = true, Distance = 9f },
            };
            var scaled = new List<string>();
            var dropped = new List<string>();
            BarkPass.Run(items, true, Read, item => dropped.Add(item.Name), (item, distance) => scaled.Add(item.Name + ":" + distance));
            Assert.Equal(new[] { "bad" }, dropped);
            Assert.Equal(new[] { "far:9", "near:1" }, scaled);
            Assert.Equal(2, items.Count);
            Assert.Equal("near", items[0].Name);
            Assert.Equal("far", items[1].Name);
        }

        [Fact]
        public void ASecondFrameDoesNotReadTheDroppedSource()
        {
            var items = new List<Item>
            {
                new Item { Name = "ok", Active = true, Distance = 1f },
                new Item { Name = "bad", ThrowOnRead = true },
            };
            int reads = 0;
            BarkPass.Run(items, true, item => { reads++; return Read(item); }, _ => { }, (_, _) => { });
            Assert.Equal(2, reads);
            reads = 0;
            BarkPass.Run(items, true, item => { reads++; return Read(item); }, _ => { }, (_, _) => { });
            Assert.Equal(1, reads);
            Assert.Equal("ok", items[0].Name);
        }

        [Fact]
        public void AnInactiveSourceIsRestoredAndNotScaled()
        {
            var items = new List<Item> { new Item { Name = "done", Active = false } };
            var scaled = new List<string>();
            var dropped = new List<string>();
            BarkPass.Run(items, true, Read, item => dropped.Add(item.Name), (item, _) => scaled.Add(item.Name));
            Assert.Equal(new[] { "done" }, dropped);
            Assert.Empty(scaled);
            Assert.Empty(items);
        }

        [Fact]
        public void WithoutAPlayerAnActiveBarkKeepsItsVolume()
        {
            var items = new List<Item> { new Item { Name = "bark", Active = true, Distance = 4f } };
            var scaled = new List<string>();
            var dropped = new List<string>();
            BarkPass.Run(items, false, Read, item => dropped.Add(item.Name), (item, _) => scaled.Add(item.Name));
            Assert.Empty(dropped);
            Assert.Empty(scaled);
            Assert.Single(items);
        }

        [Fact]
        public void AThrowingScaleDropsThatSourceAndTheEarlierOneStillScales()
        {
            var items = new List<Item>
            {
                new Item { Name = "near", Active = true, Distance = 1f },
                new Item { Name = "bad", Active = true, Distance = 3f, ThrowOnScale = true },
            };
            var scaled = new List<string>();
            var dropped = new List<string>();
            BarkPass.Run(items, true, Read, item => dropped.Add(item.Name), (item, distance) =>
            {
                if (item.ThrowOnScale) throw new InvalidOperationException("scale");
                scaled.Add(item.Name + ":" + distance);
            });
            Assert.Equal(new[] { "bad" }, dropped);
            Assert.Equal(new[] { "near:1" }, scaled);
            Assert.Equal("near", items[0].Name);
        }

        [Fact]
        public void AThrowingRestoreDoesNotStopTheNextSource()
        {
            var items = new List<Item>
            {
                new Item { Name = "near", Active = true, Distance = 1f },
                new Item { Name = "bad", ThrowOnRead = true, ThrowOnDrop = true },
            };
            var scaled = new List<string>();
            BarkPass.Run(items, true, Read, item =>
            {
                if (item.ThrowOnDrop) throw new InvalidOperationException("restore");
            }, (item, distance) => scaled.Add(item.Name + ":" + distance));
            Assert.Equal(new[] { "near:1" }, scaled);
            Assert.Single(items);
        }

        private static BarkSample Read(Item item)
        {
            if (item.ThrowOnRead) throw new InvalidOperationException("read");
            return new BarkSample { Active = item.Active, Distance = item.Distance };
        }
    }
}
