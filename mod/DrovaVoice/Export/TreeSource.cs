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
    }
}
