using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Il2CppInterop.Runtime;
using Il2CppNodeCanvas.DialogueTrees;
using MelonLoader;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

namespace DrovaVoice.Export
{
    public static class CatalogTreeLoader
    {
        /// <summary>So viele Ladeversuche je Variante entscheiden, ob sie überhaupt funktioniert.</summary>
        private const int ProbeSize = 5;

        /// <summary>
        /// Lädt jeden Baum synchron über seine Adresse. Fehler pro Baum werden gezählt, nie geworfen.
        /// Primär: LoadAssetAsync&lt;DialogueTree&gt;. Scheitern die ersten ProbeSize Versuche ohne einen einzigen Erfolg
        /// (Ausnahme oder null), wird von vorn mit LoadAssetAsync&lt;UnityEngine.Object&gt; + TryCast&lt;DialogueTree&gt;() begonnen.
        /// Scheitert auch dort die ganze Probe, wird abgebrochen.
        /// </summary>
        public static List<DialogueTree> Load(IReadOnlyList<string> addresses, MelonLogger.Instance log)
        {
            var trees = new List<DialogueTree>();
            var probe = new VariantProbe(ProbeSize);
            int failed = 0, logged = 0;
            bool gaveUp = false;
            string firstReason = "";
            for (int i = 0; i < addresses.Count; i++)
            {
                bool fallback = probe.UsingFallback;
                DialogueTree? tree = null;
                string reason = "null";
                try { tree = fallback ? LoadViaObject(addresses[i]) : LoadGeneric(addresses[i]); }
                catch (Exception e) { reason = e.GetType().Name; }
                bool ok = tree != null;
                if (ok) trees.Add(tree!);
                else
                {
                    failed++;
                    if (logged < 5)
                    {
                        logged++;
                        log.Warning($"Laden von {addresses[i]} fehlgeschlagen ({(fallback ? "Object+TryCast" : "DialogueTree")}): {reason}");
                    }
                    if (firstReason.Length == 0) firstReason = reason;
                }

                var decision = probe.OnResult(ok);
                if (decision == ProbeDecision.SwitchToFallback)
                {
                    log.Warning($"LoadAssetAsync<DialogueTree> lieferte in den ersten {ProbeSize} Versuchen keinen Erfolg (erster Grund: {firstReason}); wechsle für alle Adressen auf LoadAssetAsync<Object> + TryCast und beginne von vorn.");
                    trees.Clear();
                    failed = 0;
                    logged = 0;
                    firstReason = "";
                    i = -1;
                }
                else if (decision == ProbeDecision.GiveUp)
                {
                    log.Error($"Katalog-Laden abgebrochen: weder LoadAssetAsync<DialogueTree> noch LoadAssetAsync<Object> + TryCast lieferte in den ersten {ProbeSize} Versuchen einen Baum (letzter Grund: {firstReason}). Restliche Adressen werden nicht versucht.");
                    gaveUp = true;
                    break;
                }
                else if ((i + 1) % 200 == 0) log.Msg($"Bäume geladen: {i + 1} von {addresses.Count} (fehlgeschlagen {failed})");
            }
            log.Msg($"Katalog: {trees.Count} Bäume geladen, {failed} fehlgeschlagen, {addresses.Count} Adressen (Variante: {(probe.UsingFallback ? "Object + TryCast" : "DialogueTree")}{(gaveUp ? ", abgebrochen" : "")})");
            return trees;
        }

        private static DialogueTree? LoadGeneric(string address)
        {
            AsyncOperationHandle<DialogueTree> handle = Addressables.LoadAssetAsync<DialogueTree>(address);
            return handle.WaitForCompletion();
        }

        private static DialogueTree? LoadViaObject(string address)
        {
            AsyncOperationHandle<UnityEngine.Object> handle = Addressables.LoadAssetAsync<UnityEngine.Object>(address);
            UnityEngine.Object? obj = handle.WaitForCompletion();
            return obj?.TryCast<DialogueTree>();
        }
    }
}
