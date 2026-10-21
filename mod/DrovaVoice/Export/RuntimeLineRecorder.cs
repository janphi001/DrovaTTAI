using System;
using System.IO;
using System.Text;
using DrovaVoice.Core;
using Il2CppNodeCanvas.DialogueTrees;
using MelonLoader;

namespace DrovaVoice.Export
{
    /// <summary>
    /// Hängt jede ausgeführte Aussage ohne Indexeintrag einmal an <c>Export/&lt;Sprache&gt;/manifest-runtime.jsonl</c> an
    /// (Felder wie im Manifest des Exports). So kommen Zeilen in den Generator, die der Export nicht sieht, etwa aus Vorlagen-Bäumen,
    /// deren Loca-Pfad erst zur Laufzeit feststeht. Die Datei enthält Spieltext und bleibt im Spielordner bzw. in <c>data/</c>.
    /// </summary>
    internal sealed class RuntimeLineRecorder
    {
        private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

        private readonly string _path;
        private readonly RuntimeLineLog _log;
        private readonly MelonLogger.Instance _logger;
        private bool _failed;

        public RuntimeLineRecorder(string exportDir, MelonLogger.Instance logger)
        {
            _logger = logger;
            Directory.CreateDirectory(exportDir);
            _path = Path.Combine(exportDir, RuntimeLineLog.FileName);
            _log = new RuntimeLineLog(File.Exists(_path) ? File.ReadAllLines(_path, Utf8) : Array.Empty<string>());
        }

        public int Count => _log.Count;

        public void Record(DS_StatementNode node, string id, string locaPath)
        {
            if (_failed || _log.Contains(id)) return;
            try
            {
                string text = node.GetLocalizedString() ?? "";
                if (text.Length == 0 || text.StartsWith(DialogueExporter.KeyMissingPrefix, StringComparison.Ordinal)) return;
                string tree = node.DLGTree?.name ?? "";
                string actor = node.actorName ?? "";
                var line = new ManifestLine
                {
                    Id = id, Tree = tree, NodeId = node.ID, NodeType = "statement", ActorName = actor,
                    Category = LineClassifier.CategoryName(LineClassifier.Classify(tree, actor)),
                    Generic = LineClassifier.IsGenericActor(actor), LocaPath = LineIds.NormalizeLocaPath(locaPath),
                    LocaKey = node.statement?.locaKey ?? "", Text = text,
                };
                line.Gvars.AddRange(LineClassifier.ExtractGvars(text));
                string? json = _log.Add(line);
                if (json != null) File.AppendAllText(_path, json + "\n", Utf8);
            }
            catch (Exception e)
            {
                _failed = true;   // einmal melden, danach nicht mehr versuchen
                _logger.Warning($"Laufzeit-Zeilen: Schreiben in {_path} fehlgeschlagen ({e.GetType().Name}: {e.Message}); Sammeln aus.");
            }
        }
    }
}
