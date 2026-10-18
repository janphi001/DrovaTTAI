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
    /// <summary>Gehaltene Katalog-Bäume. <see cref="Dispose"/> gibt die Addressables-Handles frei, nachdem der Export sie gelesen hat.</summary>
    public sealed class CatalogLoad : IDisposable
    {
        private readonly MelonLogger.Instance _log;
        private readonly AssetLease _lease = new AssetLease();
        private readonly List<AsyncOperationHandle> _handles = new List<AsyncOperationHandle>();
        private bool _disposed;
        private bool _releaseWarned;

        public List<DialogueTree> Trees { get; } = new List<DialogueTree>();
        public bool GaveUp { get; internal set; }

        internal CatalogLoad(MelonLogger.Instance log) { _log = log; }

        internal bool Keep(AsyncOperationHandle handle)
        {
            if (!_lease.Keep()) return false;
            _handles.Add(handle);
            return true;
        }

        internal void DiscardBatch()
        {
            Trees.Clear();
            ReleaseKept(close: false);
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            ReleaseKept(close: true);
        }

        private void ReleaseKept(bool close)
        {
            if (close) _lease.End();
            else _lease.Discard();
            for (int i = 0; i < _handles.Count; i++) ReleaseOne(_handles[i]);
            _handles.Clear();
        }

        internal void ReleaseOne(AsyncOperationHandle handle)
        {
            try
            {
                if (handle.IsValid()) Addressables.Release(handle);
            }
            catch (Exception e)
            {
                if (_releaseWarned) return;
                _releaseWarned = true;
                _log.Warning($"Addressables-Freigabe: {e.GetType().Name}");
            }
        }
    }

    public static class CatalogTreeLoader
    {
        /// <summary>So viele Ladeversuche je Variante entscheiden, ob sie überhaupt funktioniert.</summary>
        private const int ProbeSize = 5;

        /// <summary>
        /// Lädt jeden Baum synchron über seine Adresse. Fehler pro Baum werden gezählt, nie geworfen.
        /// Primär: LoadAssetAsync&lt;DialogueTree&gt;. Scheitern die ersten ProbeSize Versuche ohne einen einzigen Erfolg
        /// (Ausnahme oder null), wird von vorn mit LoadAssetAsync&lt;UnityEngine.Object&gt; + TryCast&lt;DialogueTree&gt;() begonnen.
        /// Scheitert auch dort die ganze Probe, wird abgebrochen; <see cref="CatalogLoad.GaveUp"/> ist dann true (der Export darf nichts überschreiben).
        /// Handles erfolgreicher Bäume bleiben bis <see cref="CatalogLoad.Dispose"/> gehalten. Ein Variantenwechsel gibt die verworfene Charge sofort frei.
        /// </summary>
        public static CatalogLoad Load(IReadOnlyList<string> addresses, MelonLogger.Instance log)
        {
            var load = new CatalogLoad(log);
            try
            {
                Fill(load, addresses, log);
                return load;
            }
            catch
            {
                load.Dispose();
                throw;
            }
        }

        private static void Fill(CatalogLoad load, IReadOnlyList<string> addresses, MelonLogger.Instance log)
        {
            var probe = new VariantProbe(ProbeSize);
            int failed = 0, logged = 0;
            string firstReason = "";
            for (int i = 0; i < addresses.Count; i++)
            {
                bool fallback = probe.UsingFallback;
                DialogueTree? tree = null;
                string reason = "null";
                try { tree = fallback ? LoadViaObject(addresses[i], load) : LoadGeneric(addresses[i], load); }
                catch (Exception e) { reason = e.GetType().Name; }
                bool ok = tree != null;
                if (ok) load.Trees.Add(tree!);
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
                    load.DiscardBatch();
                    failed = 0;
                    logged = 0;
                    firstReason = "";
                    i = -1;
                }
                else if (decision == ProbeDecision.GiveUp)
                {
                    log.Error($"Katalog-Laden abgebrochen: weder LoadAssetAsync<DialogueTree> noch LoadAssetAsync<Object> + TryCast lieferte in den ersten {ProbeSize} Versuchen einen Baum (letzter Grund: {firstReason}). Restliche Adressen werden nicht versucht.");
                    load.GaveUp = true;
                    break;
                }
                else if ((i + 1) % 200 == 0) log.Msg($"Bäume geladen: {i + 1} von {addresses.Count} (fehlgeschlagen {failed})");
            }
            log.Msg($"Katalog: {load.Trees.Count} Bäume geladen, {failed} fehlgeschlagen, {addresses.Count} Adressen (Variante: {(probe.UsingFallback ? "Object + TryCast" : "DialogueTree")}{(load.GaveUp ? ", abgebrochen" : "")})");
        }

        private static DialogueTree? LoadGeneric(string address, CatalogLoad load)
        {
            AsyncOperationHandle<DialogueTree> handle = Addressables.LoadAssetAsync<DialogueTree>(address);
            try
            {
                DialogueTree? tree = handle.WaitForCompletion();
                if (tree != null && load.Keep(handle)) return tree;
                load.ReleaseOne(handle);
                return null;
            }
            catch
            {
                load.ReleaseOne(handle);
                throw;
            }
        }

        private static DialogueTree? LoadViaObject(string address, CatalogLoad load)
        {
            AsyncOperationHandle<UnityEngine.Object> handle = Addressables.LoadAssetAsync<UnityEngine.Object>(address);
            try
            {
                UnityEngine.Object? obj = handle.WaitForCompletion();
                DialogueTree? tree = obj?.TryCast<DialogueTree>();
                if (tree != null && load.Keep(handle)) return tree;
                load.ReleaseOne(handle);
                return null;
            }
            catch
            {
                load.ReleaseOne(handle);
                throw;
            }
        }
    }
}
