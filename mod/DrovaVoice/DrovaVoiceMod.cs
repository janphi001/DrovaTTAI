using System;
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

        private string ModDir => Path.Combine(MelonEnvironment.ModsDirectory, "DrovaVoice");
        private string TriggerPath => Path.Combine(ModDir, "export.trigger");

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
            if (_frame % 60 == 0 && File.Exists(TriggerPath))
            {
                try { File.Delete(TriggerPath); } catch (IOException) { }
                trigger = true;
            }
            if (!trigger && HotkeyPressed()) trigger = true;
            if (trigger) RunExport();
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

        private void RunExport()
        {
            if (_exporting) { LoggerInstance.Warning("Export läuft bereits, Auslöser ignoriert."); return; }
            _exporting = true;
            try
            {
                string lang = _language!.Value;
                var exporter = new DialogueExporter(lang, LoggerInstance);
                var manifest = exporter.Export(TreeSource.LoadedTrees());
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
