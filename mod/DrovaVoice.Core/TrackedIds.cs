using System.Collections.Generic;

namespace DrovaVoice.Core
{
    public static class TrackedIds
    {
        /// <summary>Ids aus <paramref name="tracked"/>, die in <paramref name="seen"/> fehlen. Die Anzahl allein reicht nicht.</summary>
        public static List<int> Missing(IEnumerable<int> tracked, IReadOnlySet<int> seen)
        {
            var missing = new List<int>();
            foreach (int id in tracked)
                if (!seen.Contains(id)) missing.Add(id);
            return missing;
        }
    }
}
