using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using DrovaVoice.Core;
using Drova_Modding_API.Systems.Audio;
using Drova_Modding_API.Systems.WorldEvents;
using Il2CppCustomFramework.Localization;
using DrovaVoice.Export;
using DrovaVoice.Playback;
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
        private bool _exportNpcsTriggerStuck;
        private VoiceService? _voice;
        private bool _connectorInstalled;
        private bool _connectorFailed;
        private AudioSourceScan? _sources;
        private bool _sourceScanWarned;
        private StaleAudioProbe? _probe;
        private BarkDistance? _barkDistance;
        private VoiceMenu? _menu;
        private VoiceSettings? _bootSettings;
        private bool _barkProbe;
        private readonly IndexWatch _indexWatch = new IndexWatch();
        private bool _reloadTriggerStuck;
        private bool _indexIoLogged;

        private string ModDir => Path.Combine(MelonEnvironment.ModsDirectory, "DrovaVoice");
        private string TriggerPath => Path.Combine(ModDir, "export.trigger");
        private string TriggerAllPath => Path.Combine(ModDir, "export-all.trigger");
        private string TriggerNpcsPath => Path.Combine(ModDir, "export-npcs.trigger");
        private string ReloadTriggerPath => Path.Combine(ModDir, "reload.trigger");

        public override void OnInitializeMelon()
        {
            var category = MelonPreferences.CreateCategory("DrovaVoice");
            _language = category.CreateEntry("ExportLanguage", "de", description: "Sprache des Exports (Ordnername)");
            var enabled = category.CreateEntry("Enabled", true, description: "Vertonung an/aus");
            var dialogVolume = category.CreateEntry("DialogVolume", 100, description: "Lautstärke NPC-Stimmen in Prozent (0-200, über 100 = Verstärkung)");
            var playerVolume = category.CreateEntry("PlayerVolume", 100, description: "Lautstärke Spielerzeilen in Prozent (0-200, über 100 = Verstärkung)");
            var barkVolume = category.CreateEntry("BarkVolume", 100, description: "Lautstärke Welt-Kommentare in Prozent (0-200, über 100 = Verstärkung)");
            var barkProbe = category.CreateEntry("BarkProbe", false, description: "Probe: Figur jeder Aussage loggen (nur für die Entwicklung)");
            var barkMin = category.CreateEntry("BarkMinDistance", VoiceSettings.DefaultBarkMinDistance, description: "Barks: bis zu diesem Abstand in Weltmetern volle Lautstärke");
            var barkMax = category.CreateEntry("BarkMaxDistance", VoiceSettings.DefaultBarkMaxDistance, description: "Barks: ab diesem Abstand stumm, dazwischen linear leiser");
            var audioLanguage = category.CreateEntry("AudioLanguage", "de", description: "Unterordner unter Mods/DrovaVoice/Audio");
            var cacheMb = category.CreateEntry("CacheMB", 64, description: "Obergrenze für geladene Clips in MB (8-512)");
            var diagnostics = category.CreateEntry("Diagnostics", false, description: "Jede Zeile einmal loggen (geladen/ohne Eintrag)");
            Directory.CreateDirectory(ModDir);
            string probe = LineIds.AudioFileName(LineIds.Statement("DT_Main_NPC_Adela", "Dialog/NPC_Adela", "Plh_5"));
            LoggerInstance.Msg($"DrovaVoice {Info.Version} geladen (Core ok: {probe}). Export: Datei export.trigger in {ModDir} anlegen oder F9 drücken. Index neu: reload.trigger, oder wenn sich index.json ändert.");

            WarnIfDrovaTtsLoaded();

            var warnings = new List<string>();
            var settings = VoiceSettings.Create(enabled.Value, dialogVolume.Value, playerVolume.Value, audioLanguage.Value, cacheMb.Value, diagnostics.Value, warnings, barkVolume.Value, barkMin.Value, barkMax.Value);
            foreach (string w in warnings) LoggerInstance.Warning(w);
            _bootSettings = settings;
            _barkProbe = barkProbe.Value;
            if (!settings.Enabled) LoggerInstance.Msg("Vertonung ist ausgeschaltet (Enabled=false); im Optionsmenü wieder einschaltbar.");
            PollIndex(force: false);   // ChoiceHook.Service folgt erst, wenn der Connector ersetzt ist
        }

        /// <summary>Melon-Name von DrovaTTS ist „Drova TTS“, die Assembly heißt DrovaTTS. Eines von beiden reicht für die Warnung.</summary>
        private void WarnIfDrovaTtsLoaded()
        {
            try
            {
                var melonNames = new List<string>();
                foreach (MelonBase melon in MelonBase.RegisteredMelons)
                {
                    string? name = melon.Info?.Name;
                    if (name != null) melonNames.Add(name);
                }
                var assemblyNames = new List<string>();
                foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    string? name = asm.GetName().Name;
                    if (name != null) assemblyNames.Add(name);
                }
                if (ModConflict.DrovaTtsLoaded(melonNames, assemblyNames))
                    LoggerInstance.Warning(ModConflict.DrovaTtsWarning);
            }
            catch (Exception e)
            {
                LoggerInstance.Warning($"DrovaTTS-Prüfung fehlgeschlagen ({e.GetType().Name}). Ob beide Mods denselben Connector ersetzen, bleibt ungewiss.");
            }
        }

        /// <summary>
        /// Liest index.json neu, wenn sich Länge oder Schreibzeit geändert haben oder reload.trigger liegt.
        /// Fehlt die Datei oder schlägt das Lesen fehl, steht das einmal im Log. Ein schon geladener Index bleibt dabei erhalten.
        /// </summary>
        private void PollIndex(bool force)
        {
            if (_bootSettings == null) return;
            string path = Path.Combine(ModDir, "Audio", _bootSettings.Language, "index.json");
            bool exists;
            FileStamp? stamp = null;
            try
            {
                exists = IndexWatch.TryReadStamp(path, out var read);
                if (exists) stamp = read;
                _indexIoLogged = false;
            }
            catch (Exception e)
            {
                if (!_indexIoLogged)
                {
                    _indexIoLogged = true;
                    LoggerInstance.Error(IndexMessages.Unreadable(e));
                }
                return;
            }

            IndexWatchStep step = _indexWatch.Poll(exists, stamp, force);
            if (step.Action == IndexWatchAction.None) return;
            if (step.Action == IndexWatchAction.Missing)
            {
                if (step.Log)
                    LoggerInstance.Warning(_indexWatch.HasIndex ? IndexMessages.MissingKept(path) : IndexMessages.Missing(path));
                return;
            }

            try
            {
                var index = AudioIndex.Parse(File.ReadAllText(path), _bootSettings.Language);
                if (_voice == null)
                {
                    string root = Path.Combine(ModDir, "Audio", _bootSettings.Language);
                    _voice = new VoiceService(index, root, _bootSettings, LoggerInstance) { ProbeFigures = _barkProbe };
                    LoggerInstance.Msg(IndexMessages.FirstLoad(index.Count, index.Skipped, _bootSettings.DialogPercent, _bootSettings.PlayerPercent, _bootSettings.BarkPercent, _bootSettings.CacheMegabytes));
                }
                else
                {
                    _voice.ReplaceIndex(index);
                    LoggerInstance.Msg(IndexMessages.Reloaded(index.Count, index.Skipped));
                }
                if (stamp is FileStamp loaded) _indexWatch.NoteLoaded(loaded);
            }
            catch (Exception e)
            {
                if (step.Log)
                    LoggerInstance.Error(_indexWatch.HasIndex ? IndexMessages.ReloadFailed(e) : IndexMessages.Unusable(e));
                _indexWatch.NoteFailure(stamp);
            }
        }

        /// <summary>
        /// AudioManager der API legt in seinem statischen Konstruktor einen Provider an, der WorldEventSystemManager.Instance braucht;
        /// im Hauptmenü ist die noch null, und ein fehlgeschlagener statischer Konstruktor bleibt dauerhaft kaputt.
        /// Deshalb wird der Connector erst ersetzt, wenn die Instanz existiert.
        /// </summary>
        private void TryInstallConnector()
        {
            if (_voice == null || _connectorInstalled || _connectorFailed) return;
            if (WorldEventSystemManager.Instance == null) return;
            try
            {
                AudioManager.ReplaceDialogueAudioConnector(new VoiceConnector(_voice));
                _connectorInstalled = true;
                _sources = new AudioSourceScan();
                _probe = new StaleAudioProbe(LoggerInstance, _voice.Diagnostics);
                _barkDistance = new BarkDistance(_voice.BarkMinDistance, _voice.BarkMaxDistance, LoggerInstance, _voice.Diagnostics);
                _voice.BarkDistance = _barkDistance;
                ChoiceHook.Service = _voice;   // vor dem Menü: ein Menüfehler darf die Auswahloptionen und die Installation nicht kippen
                try { SetUpMenu(); } catch (Exception e) { LoggerInstance.Warning($"Optionsmenü nicht verfügbar ({e.GetType().Name}). Die Einstellungen aus MelonPreferences.cfg gelten weiter."); }
                LoggerInstance.Msg("Audio-Connector der Modding API ersetzt.");
            }
            catch (Exception e)
            {
                _connectorFailed = true;
                LoggerInstance.Error($"Connector konnte nicht ersetzt werden, Vertonung bleibt aus: {e.GetType().Name}: {e.Message}");
            }
        }

        /// <summary>Optionsmenü einrichten. Eigene Methode ohne Inlining: Fehlt ein API-Typ, scheitert schon das JIT dieser Methode, und der Aufrufer fängt es hier ab.</summary>
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        private void SetUpMenu()
        {
            try
            {
                _menu = new VoiceMenu(_voice!, LoggerInstance);
                _menu.Register();
                _menu.LoadFromConfig();
            }
            catch (Exception e)
            {
                LoggerInstance.Warning($"Optionsmenü nicht verfügbar ({e.GetType().Name}: {e.Message}). Die Einstellungen aus MelonPreferences.cfg gelten weiter.");
            }
        }

        public override void OnUpdate()
        {
            _frame++;
            if (!_connectorInstalled) TryInstallConnector();   // billig: nur ein statischer Null-Test pro Frame bis zur Installation
            if (_sources != null)
            {
                try { _sources.Tick(Time.unscaledTime); }
                catch (Exception e) { WarnSourceScan(e); }
                _probe?.Observe(_sources);
                _barkDistance?.Update(_sources.Sources, Time.unscaledTime);
            }
            bool trigger = false;
            if (_frame % 60 == 0)
            {
                if (ConsumeTrigger(TriggerPath, ref _exportTriggerStuck)) trigger = true;
                PollIndex(ConsumeTrigger(ReloadTriggerPath, ref _reloadTriggerStuck));
            }
            if (!trigger && HotkeyPressed()) trigger = true;
            bool all = _frame % 60 == 0 && ConsumeTrigger(TriggerAllPath, ref _exportAllTriggerStuck);
            if (all) RunExport(useCatalog: true);
            else if (trigger) RunExport(useCatalog: false);
            if (_frame % 60 == 30 && ConsumeTrigger(TriggerNpcsPath, ref _exportNpcsTriggerStuck))
            {
                try { NpcExporter.Export(Path.Combine(ModDir, "Export", ExportLanguageFolder()), LoggerInstance); }
                catch (Exception e) { LoggerInstance.Error($"NPC-Export fehlgeschlagen: {e}"); }
                try { TeacherExporter.Export(Path.Combine(ModDir, "Export", _language!.Value), LoggerInstance); }
                catch (Exception e) { LoggerInstance.Error($"Lehrer-Export fehlgeschlagen: {e}"); }
            }
        }

        private void WarnSourceScan(Exception e)
        {
            if (_sourceScanWarned) return;
            _sourceScanWarned = true;
            LoggerInstance.Warning($"Audioquellen-Suche: {e.GetType().Name}: {e.Message}");
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

        private string ExportLanguageFolder()
        {
            var warnings = new List<string>();
            string lang = VoiceSettings.CleanFolderName(_language?.Value, "ExportLanguage", warnings);
            foreach (string warning in warnings) LoggerInstance.Warning(warning);
            return lang;
        }

        private void LogLanguage(string preference)
        {
            string current;
            try { current = LocalizationDB.Instance.CurrentLanguage.ToString(); }
            catch (Exception e)
            {
                LoggerInstance.Warning($"Spielsprache nicht lesbar ({e.GetType().Name}); ExportLanguage ist '{preference}'.");
                return;
            }
            LoggerInstance.Msg($"Spielsprache: {current}, ExportLanguage: {preference}");
            if (!LanguageCheck.Matches(current, preference))
                LoggerInstance.Warning($"Spielsprache '{current}' weicht von ExportLanguage '{preference}' ab: Der Text im Manifest kommt in der Spielsprache, liegt aber im Ordner '{preference}'.");
        }

        private void RunExport(bool useCatalog)
        {
            if (_exporting) { LoggerInstance.Warning("Export läuft bereits, Auslöser ignoriert."); return; }
            _exporting = true;
            CatalogLoad? catalogLoad = null;
            try
            {
                if (_voice != null && !_connectorInstalled && WorldEventSystemManager.Instance == null)
                    LoggerInstance.Warning("Export im Hauptmenü: Die Modding API scheitert dabei beim Initialisieren ihres AudioManagers; die Vertonung bleibt in dieser Sitzung aus. Zum Hören das Spiel neu starten.");
                string lang = ExportLanguageFolder();
                LogLanguage(lang);
                var exporter = new DialogueExporter(lang, LoggerInstance);
                IEnumerable<Il2CppNodeCanvas.DialogueTrees.DialogueTree> trees;
                int? addressCount = null;
                if (useCatalog)
                {
                    string catalog = Path.Combine(MelonEnvironment.GameRootDirectory, "Drova_Data", "StreamingAssets", "aa", "catalog.json");
                    if (!File.Exists(catalog))
                    {
                        LoggerInstance.Error($"Addressables-Katalog nicht gefunden: {catalog}");
                        return;
                    }
                    var addresses = CatalogReader.TreeAddresses(File.ReadAllText(catalog));
                    addressCount = addresses.Count;
                    LoggerInstance.Msg($"Katalog: {addresses.Count} Baum-Adressen");
                    catalogLoad = CatalogTreeLoader.Load(addresses, LoggerInstance);
                    int fromCatalog = catalogLoad.Trees.Count;
                    trees = TreeSource.CatalogUnionLoaded(catalogLoad.Trees, out int addedLoaded);
                    LoggerInstance.Msg($"Bäume: {fromCatalog} aus dem Katalog, {addedLoaded} zusätzlich aus dem Speicher");
                }
                else trees = TreeSource.LoadedTrees();
                var manifest = exporter.Export(trees);
                string path = Path.Combine(ModDir, "Export", lang, useCatalog ? ManifestFile.FullName : ManifestFile.LoadedName);
                bool loaderGaveUp = catalogLoad != null && catalogLoad.GaveUp;
                string? blocked = ExportGuard.ShouldSave(manifest.Lines.Count, loaderGaveUp, addressCount);
                if (blocked != null)
                {
                    LoggerInstance.Error($"Manifest NICHT geschrieben ({blocked}); eine vorhandene {Path.GetFileName(path)} bleibt unverändert: {path}");
                    return;
                }
                ManifestFile.Save(manifest, path);
                LoggerInstance.Msg($"Manifest geschrieben: {path} ({manifest.Lines.Count} Zeilen)");
            }
            catch (Exception e)
            {
                LoggerInstance.Error($"Export fehlgeschlagen: {e}");
            }
            finally
            {
                catalogLoad?.Dispose();
                _exporting = false;
            }
        }
    }
}
