using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Buchführung für den Clip-Cache: zuletzt benutzte Einträge zuerst behalten, am wenigsten benutzte zuerst verdrängen,
    /// bis die Summe der Bytes im Budget liegt. Die jüngsten <c>protectedRecent</c> Einträge werden nie verdrängt (sie können
    /// gerade abgespielt werden), auch wenn sie allein das Budget überschreiten.
    /// </summary>
    public sealed class ClipBudget
    {
        private readonly long _maxBytes;
        private readonly int _protectedRecent;
        private readonly LinkedList<string> _order = new LinkedList<string>(); // vorn = jüngster
        private readonly Dictionary<string, (LinkedListNode<string> Node, long Bytes)> _items =
            new Dictionary<string, (LinkedListNode<string>, long)>(StringComparer.Ordinal);

        public ClipBudget(long maxBytes, int protectedRecent)
        {
            _maxBytes = maxBytes;
            _protectedRecent = protectedRecent < 1 ? 1 : protectedRecent;
        }

        public long TotalBytes { get; private set; }
        public int Count => _items.Count;

        public bool Contains(string key) => _items.ContainsKey(key);

        public void Touch(string key)
        {
            if (!_items.TryGetValue(key, out var item)) return;
            _order.Remove(item.Node);
            _order.AddFirst(item.Node);
        }

        /// <summary>Fügt ein oder aktualisiert einen Eintrag und liefert die verdrängten Schlüssel.</summary>
        public IReadOnlyList<string> Add(string key, long bytes)
        {
            if (bytes < 0) throw new ArgumentOutOfRangeException(nameof(bytes));
            Remove(key);
            var node = _order.AddFirst(key);
            _items[key] = (node, bytes);
            TotalBytes += bytes;

            var evicted = new List<string>();
            while (TotalBytes > _maxBytes && _order.Count > _protectedRecent)
            {
                var last = _order.Last!;
                _order.RemoveLast();
                var item = _items[last.Value];
                _items.Remove(last.Value);
                TotalBytes -= item.Bytes;
                evicted.Add(last.Value);
            }
            return evicted;
        }

        public void Remove(string key)
        {
            if (!_items.TryGetValue(key, out var item)) return;
            _order.Remove(item.Node);
            _items.Remove(key);
            TotalBytes -= item.Bytes;
        }
    }
}
