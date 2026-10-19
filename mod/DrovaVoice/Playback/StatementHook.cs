using System;
using DrovaVoice.Core;
using HarmonyLib;
using Il2CppNodeCanvas.DialogueTrees;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Läuft vor dem API-Prefix auf dem Aussageknoten. Der API-Prefix ruft den Connector nur auf,
    /// wenn noch kein Clip hängt. Zwei Figuren derselben Aussage im selben Frame kämen sonst nicht beide dran.
    /// </summary>
    [HarmonyPatch(typeof(DS_StatementNode), "OnExecute")]
    internal static class StatementHook
    {
        [HarmonyPriority(StatementGate.BeforeApiPrefix)]
        private static void Prefix(DS_StatementNode __instance)
        {
            try
            {
                if (__instance == null) return;
                var statement = __instance.statement;
                if (statement == null) return;
                var clip = statement.audio;
                if (clip != null && StatementGate.ClearAttachedClip(clip.name, ClipLoader.ClipNamePrefix))
                    statement.audio = null;
            }
            catch (Exception e)
            {
                var service = ChoiceHook.Service;
                if (service != null) service.LogError("StatementHook", null, e);
            }
        }
    }
}
