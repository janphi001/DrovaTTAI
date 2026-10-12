using System;
using System.Collections.Generic;
using Il2CppInterop.Runtime;
using Il2CppNodeCanvas.DialogueTrees;
using MelonLoader;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

namespace DrovaVoice.Export
{
    public static class CatalogTreeLoader
    {
        /// <summary>
        /// Lädt jeden Baum synchron über seine Adresse. Fehler pro Baum werden gezählt, nie geworfen.
        /// Primär: LoadAssetAsync&lt;DialogueTree&gt;. Wirft der Aufruf für die erste Adresse eine Il2Cpp-/NotSupported-/
        /// ExecutionEngine-artige Ausnahme (generische Instanz dem Spiel unbekannt), wird für alle Adressen auf
        /// LoadAssetAsync&lt;UnityEngine.Object&gt; + TryCast&lt;DialogueTree&gt;() umgeschaltet.
        /// </summary>
        public static List<DialogueTree> Load(IReadOnlyList<string> addresses, MelonLogger.Instance log)
        {
            var trees = new List<DialogueTree>();
            int failed = 0;
            bool useFallback = false;
            for (int i = 0; i < addresses.Count; i++)
            {
                try
                {
                    DialogueTree? tree;
                    if (i == 0 && !useFallback)
                    {
                        try { tree = LoadGeneric(addresses[i]); }
                        catch (Exception e) when (IsGenericInstanceProblem(e))
                        {
                            useFallback = true;
                            log.Warning($"LoadAssetAsync<DialogueTree> nicht nutzbar ({e.GetType().Name}); wechsle für alle Adressen auf LoadAssetAsync<Object> + TryCast.");
                            tree = LoadViaObject(addresses[i]);
                        }
                    }
                    else tree = useFallback ? LoadViaObject(addresses[i]) : LoadGeneric(addresses[i]);
                    if (tree != null) trees.Add(tree); else failed++;
                }
                catch (Exception e)
                {
                    failed++;
                    if (failed <= 5) log.Warning($"Laden von {addresses[i]} fehlgeschlagen: {e.GetType().Name}: {e.Message}");
                }
                if ((i + 1) % 200 == 0) log.Msg($"Bäume geladen: {i + 1} von {addresses.Count} (fehlgeschlagen {failed})");
            }
            log.Msg($"Katalog: {trees.Count} Bäume geladen, {failed} fehlgeschlagen, {addresses.Count} Adressen{(useFallback ? " (Variante: Object + TryCast)" : "")}");
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

        private static bool IsGenericInstanceProblem(Exception e) =>
            e is NotSupportedException || e is MissingMethodException
            || e is TypeLoadException || e is NotImplementedException
            || e.GetType().Name == "ExecutionEngineException" // veralteter Typ, nur per Namen geprüft
            || e.GetType().Name.StartsWith("Il2Cpp", StringComparison.Ordinal);
    }
}
