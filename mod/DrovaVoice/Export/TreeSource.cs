using System.Collections.Generic;
using Il2CppNodeCanvas.DialogueTrees;
using UnityEngine;

namespace DrovaVoice.Export
{
    public static class TreeSource
    {
        /// <summary>Alle zurzeit im Speicher befindlichen Dialogbäume.</summary>
        public static IEnumerable<DialogueTree> LoadedTrees()
        {
            var trees = Resources.FindObjectsOfTypeAll<DialogueTree>();
            for (int i = 0; i < trees.Length; i++) yield return trees[i];
        }

        /// <summary>Hängt an die Katalog-Bäume die geladenen an (<paramref name="added"/> = Anzahl), die dort noch nicht (nach Baumname) vorkommen; so wird derselbe Baum nicht doppelt deserialisiert.</summary>
        public static List<DialogueTree> CatalogUnionLoaded(List<DialogueTree> catalogTrees, out int added)
        {
            var names = new HashSet<string>(System.StringComparer.Ordinal);
            foreach (var tree in catalogTrees) names.Add(NameOf(tree));
            added = 0;
            foreach (var tree in LoadedTrees())
            {
                if (tree == null) continue;
                if (!names.Add(NameOf(tree))) continue;
                catalogTrees.Add(tree);
                added++;
            }
            return catalogTrees;
        }

        private static string NameOf(DialogueTree tree)
        {
            try { return tree.name; } catch (System.Exception) { return "?" + System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(tree); }
        }
    }
}
