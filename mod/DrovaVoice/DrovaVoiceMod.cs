using System;
using System.Collections.Generic;
using System.IO;
using DrovaVoice.Core;
using DrovaVoice.Export;
using MelonLoader;
using MelonLoader.Utils;
using UnityEngine;

[assembly: MelonInfo(typeof(DrovaVoice.DrovaVoiceMod), "DrovaVoice", "0.1.0", "janphi001")]
[assembly: MelonGame("Just2D", "Drova")]
[assembly: MelonAdditionalDependencies("Drova_Modding_API")]

namespace DrovaVoice
{
    public sealed class DrovaVoiceMod : MelonMod
    {
        private MelonPreferences_Entry<string>? _language;
        private bool _exporting;
        private bool _hotkeyBroken;
        private int _frame;
        private bool _exportTriggerStuck;
        private bool _exportAllTriggerStuck;

        private string ModDir => Path.Combine(MelonEnvironment.ModsDirectory, "DrovaVoice");
        private string TriggerPath => Path.Combine(ModDir, "export.trigger");
        private string TriggerAllPath => Path.Combine(ModDir, "export-all.trigger");

        public override void OnInitializeMelon()
        {
            _language = MelonPreferences.CreateCategory("DrovaVoice").CreateEntry("ExportLanguage", "de", description: "Sprache des Exports (Ordnername)");
            Directory.CreateDirectory(ModDir);
            string probe = LineIds.AudioFileName(LineIds.Statement("DT_Main_NPC_Adela", "Dialog/NPC_Adela", "Plh_5"));
            LoggerInstance.Msg($"DrovaVoice {Info.Version} geladen (Core ok: {probe}). Export: Datei export.trigger in {ModDir} anlegen oder F9 drücken.");
        }

        public override void OnUpdate()
        {
            _frame++;
            bool trigger = false;
            if (_frame % 60 == 0 && ConsumeTrigger(TriggerPath, ref _exportTriggerStuck)) trigger = true;
            if (!trigger && HotkeyPressed()) trigger = true;
            bool all = _frame % 60 == 0 && ConsumeTrigger(TriggerAllPath, ref _exportAllTriggerStuck);
            if (all) RunExport(useCatalog: true);
            else if (trigger) RunExport(useCatalog: false);
        }

        /// <summary>True genau einmal pro Auslöser-Datei: Datei löschen und melden. Lässt sie sich nicht löschen, wird einmal gewarnt und nicht erneut ausgelöst, bis die Datei weg ist.</summary>
        private bool ConsumeTrigger(string path, ref bool stuck)
        {
            try
            {
                if (!File.Exists(path)) { stuck = false; return false; }
                if (stuck) return false;
                try { File.Delete(path); } catch (Exception) { }
                if (!File.Exists(path)) return true;
            }
            catch (Exception) { }
            stuck = true;
            LoggerInstance.Warning($"Auslöser-Datei {Path.GetFileName(path)} lässt sich nicht löschen; kein erneuter Auslöser, bis sie entfernt ist.");
            return false;
        }

        private bool HotkeyPressed()
        {
            if (_hotkeyBroken) return false;
            try { return Input.GetKeyDown(KeyCode.F9); }
            catch (Exception e)
            {
                _hotkeyBroken = true;
                LoggerInstance.Warning($"F9 nicht verfügbar ({e.GetType().Name}); nur die Trigger-Datei funktioniert.");
                return false;
            }
        }

        private void RunExport(bool useCatalog)
        {
            if (_exporting) { LoggerInstance.Warning("Export läuft bereits, Auslöser ignoriert."); return; }
            _exporting = true;
            try
            {
                string lang = _language!.Value;
                var exporter = new DialogueExporter(lang, LoggerInstance);
                IEnumerable<Il2CppNodeCanvas.DialogueTrees.DialogueTree> trees;
                if (useCatalog)
                {
                    string catalog = Path.Combine(MelonEnvironment.GameRootDirectory, "Drova_Data", "StreamingAssets", "aa", "catalog.json");
                    if (!File.Exists(catalog))
                    {
                        LoggerInstance.Error($"Addressables-Katalog nicht gefunden: {catalog}");
                        return;
                    }
                    var addresses = CatalogReader.TreeAddresses(File.ReadAllText(catalog));
                    LoggerInstance.Msg($"Katalog: {addresses.Count} Baum-Adressen");
                    trees = CatalogTreeLoader.Load(addresses, LoggerInstance);
                }
                else trees = TreeSource.LoadedTrees();
                var manifest = exporter.Export(trees);
                string path = Path.Combine(ModDir, "Export", lang, "manifest.json");
                ManifestFile.Save(manifest, path);
                LoggerInstance.Msg($"Manifest geschrieben: {path} ({manifest.Lines.Count} Zeilen)");
            }
            catch (Exception e)
            {
                LoggerInstance.Error($"Export fehlgeschlagen: {e}");
            }
            finally
            {
                _exporting = false;
            }
        }
    }
}
