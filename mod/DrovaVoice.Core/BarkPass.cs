using System;
using System.Collections.Generic;

namespace DrovaVoice.Core
{
    public readonly struct BarkSample
    {
        public bool Active { get; init; }
        public float Distance { get; init; }
    }

    /// <summary>
    /// Ein Frame der Bark-Regelung. Eine Quelle, die sich nicht lesen oder nicht regeln lässt, fällt aus der Liste,
    /// und die übrigen Quellen dieses Frames laufen weiter.
    /// </summary>
    public static class BarkPass
    {
        public static void Run<T>(IList<T> tracked, bool havePlayer, Func<T, BarkSample> read, Action<T> drop, Action<T, float> scale)
        {
            for (int i = tracked.Count - 1; i >= 0; i--)
            {
                T item = tracked[i];
                BarkSample sample;
                try { sample = read(item); }
                catch (Exception)
                {
                    SafeDrop(drop, item);
                    tracked.RemoveAt(i);
                    continue;
                }
                if (!sample.Active)
                {
                    SafeDrop(drop, item);
                    tracked.RemoveAt(i);
                    continue;
                }
                if (!havePlayer) continue;
                try { scale(item, sample.Distance); }
                catch (Exception)
                {
                    SafeDrop(drop, item);
                    tracked.RemoveAt(i);
                }
            }
        }

        private static void SafeDrop<T>(Action<T> drop, T item)
        {
            try { drop(item); }
            catch (Exception) { }
        }
    }
}
