using System;
using DrovaVoice.Core;
using HarmonyLib;
using Il2CppNodeCanvas.DialogueTrees;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Die API spielt eine gewählte Option nur mit Ton, wenn choice.statement.audio schon gesetzt ist; ihr eigener Handler
    /// für Auswahlknoten ist leer. Deshalb laden wir die Clips aller Optionen, bevor der Knoten ausgeführt (angezeigt) wird.
    /// </summary>
    [HarmonyPatch(typeof(DS_MultipleChoiceNode), "OnExecute")]
    internal static class ChoiceHook
    {
        /// <summary>null = Vertonung aus; der Prefix tut dann nichts.</summary>
        public static VoiceService? Service;

        private static void Prefix(DS_MultipleChoiceNode __instance)
        {
            var service = Service;
            if (service == null) return;
            try
            {
                var tree = __instance.DLGTree;
                var choices = __instance.availableChoices;
                for (int k = 0; k < choices.Count; k++)
                {
                    try   // je Option: ein Fehler (z. B. leerer Schlüssel) lässt die übrigen Optionen nicht aus
                    {
                        var statement = choices[k].statement;
                        if (statement.audio != null) continue;
                        string locaPath = statement.useGlobalLoca ? statement.GlobalLocaPath : tree.LocaPath;
                        string id = LineIds.Choice(tree.name, locaPath, statement.locaKey, k);
                        var clip = service.GetClip(id);
                        if (clip != null) statement.audio = clip;
                    }
                    catch (Exception e) { service.LogError("ChoiceHook", e); }
                }
            }
            catch (Exception e) { service.LogError("ChoiceHook", e); }
        }
    }
}
