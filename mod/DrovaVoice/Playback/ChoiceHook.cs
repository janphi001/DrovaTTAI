using System;
using DrovaVoice.Core;
using HarmonyLib;
using Il2CppNodeCanvas.DialogueTrees;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Die API spielt eine gewählte Option nur mit Ton, wenn choice.statement.audio schon gesetzt ist; ihr eigener Handler
    /// für Auswahlknoten ist leer. Deshalb laden wir die Clips aller Optionen, bevor der Knoten ausgeführt (angezeigt) wird.
    /// Nur bei Knoten, die die Auswahl laut Spiel sprechen (saySelection): sonst würde die API sie plötzlich sprechen lassen.
    /// </summary>
    [HarmonyPatch(typeof(DS_MultipleChoiceNode), "OnExecute")]
    internal static class ChoiceHook
    {
        /// <summary>
        /// null = aus. Wird erst gesetzt, nachdem der Connector der API ersetzt wurde: Ein gesetztes Optionsaudio schickt die API
        /// über ihren AudioManager, der ohne erfolgreiche Initialisierung Ausnahmen wirft.
        /// </summary>
        public static VoiceService? Service;

        private static void Prefix(DS_MultipleChoiceNode __instance)
        {
            var service = Service;
            if (service == null) return;
            try
            {
                var tree = __instance.DLGTree;
                if (!__instance.saySelection)
                {
                    service.Diag("nosay|" + tree.name + "|" + __instance.ID, $"[Zeile] Auswahlknoten {__instance.ID} in '{tree.name}' spricht die Auswahl nicht (saySelection aus)");
                    return;
                }
                var choices = __instance.availableChoices;
                for (int k = 0; k < choices.Count; k++)
                {
                    string? id = null;
                    try   // je Option: ein Fehler lässt die übrigen Optionen nicht aus
                    {
                        var statement = choices[k].statement;
                        if (statement.audio != null) continue;
                        string locaPath = LineIds.ResolveLocaPath(statement.useGlobalLoca, statement.GlobalLocaPath, tree.LocaPath);
                        if (!LineIds.TryStatement(tree.name, locaPath, statement.locaKey, out string statementId)
                            || !LineIds.TryChoice(tree.name, locaPath, statement.locaKey, k, out string choiceId))
                        {
                            service.Diag("bad|" + tree.name + "|" + statement.locaKey, $"[Zeile] keine gültige ID (Baum '{tree.name}', Schlüssel '{statement.locaKey}')");
                            continue;
                        }
                        id = choiceId;
                        var clip = service.GetChoiceClip(statementId, choiceId);
                        if (clip != null) statement.audio = clip;
                    }
                    catch (Exception e) { service.LogError("ChoiceHook", id, e); }
                }
            }
            catch (Exception e) { service.LogError("ChoiceHook", null, e); }
        }
    }
}
