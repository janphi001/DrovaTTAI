using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Il2CppNodeCanvas.DialogueTrees;
using Il2CppNodeCanvas.Framework;
using MelonLoader;

namespace DrovaVoice.Export
{
    public sealed class ExportStats
    {
        public int Trees, TreesFailed, TreesSkipped, Statements, Choices, SkippedUnused, SkippedDuplicates, SkippedInvalid, SkippedErrors;
        public override string ToString()
            => $"Bäume {Trees} (fehlgeschlagen {TreesFailed}, übersprungen {TreesSkipped}); Aussagen {Statements}, Optionen {Choices}; "
             + $"ohne Text/unbenutzt {SkippedUnused}, doppelt {SkippedDuplicates}, ungültige ID {SkippedInvalid}, Fehler {SkippedErrors}";
    }

    public sealed class DialogueExporter
    {
        private const string KeyMissingPrefix = "[LOCA] Key not found";
        private readonly string _language;
        private const int MaxErrorLogs = 5;
        private readonly MelonLogger.Instance _log;
        public ExportStats Stats { get; } = new ExportStats();

        public DialogueExporter(string language, MelonLogger.Instance log)
        {
            _language = language;
            _log = log;
        }

        public Manifest Export(IEnumerable<DialogueTree> trees)
        {
            var manifest = new Manifest { Language = _language };
            var seen = new HashSet<string>();
            foreach (var tree in trees)
            {
                if (tree == null) continue;
                try
                {
                    if (tree.IsTestOrDebugDialogue) { Stats.TreesSkipped++; continue; }
                    ExportTree(tree, manifest.Lines, seen);
                    Stats.Trees++;
                }
                catch (Exception e)
                {
                    Stats.TreesFailed++;
                    _log.Warning($"Baum {SafeName(tree)} nicht exportiert: {e.GetType().Name}: {e.Message}");
                }
            }
            _log.Msg("Export fertig: " + Stats + $"; Zeilen im Manifest {manifest.Lines.Count}");
            return manifest;
        }

        private static string SafeName(DialogueTree tree)
        {
            try { return tree.name; } catch { return "?"; }
        }

        private void ExportTree(DialogueTree tree, List<ManifestLine> lines, HashSet<string> seen)
        {
            tree.SelfDeserialize();
            tree.DeserializeIfNotDoneYet(true);
            string treeName = tree.name;
            string treeLoca = tree.LocaPath ?? "";
            var nodes = tree.allNodes;
            for (int i = 0; i < nodes.Count; i++)
            {
                try
                {
                    Node node = nodes[i];
                    if (node == null) continue;
                    var statement = node.TryCast<DS_StatementNode>();
                    if (statement != null) { AddStatement(treeName, treeLoca, statement, lines, seen); continue; }
                    var choiceNode = node.TryCast<DS_MultipleChoiceNode>();
                    if (choiceNode != null) AddChoices(treeName, treeLoca, choiceNode, lines, seen);
                }
                catch (Exception e)
                {
                    LineError(treeName, e);
                }
            }
        }

        private void LineError(string treeName, Exception e)
        {
            Stats.SkippedErrors++;
            if (Stats.SkippedErrors <= MaxErrorLogs)
                _log.Warning($"Zeile in Baum {treeName} übersprungen: {e.GetType().Name}");
        }

        private void AddStatement(string treeName, string treeLoca, DS_StatementNode node, List<ManifestLine> lines, HashSet<string> seen)
        {
            var st = node.statement;
            string key = st.locaKey;
            string locaPath = st.useGlobalLoca ? st.GlobalLocaPath : treeLoca;
            string text = node.GetLocalizedString();
            if (string.IsNullOrEmpty(key) || string.IsNullOrEmpty(text) || text.StartsWith(KeyMissingPrefix, StringComparison.Ordinal))
            {
                Stats.SkippedUnused++;
                return;
            }
            string actor = node.actorName ?? "";
            if (!TryAdd(lines, seen, LineIdsSafe(() => LineIds.Statement(treeName, locaPath, key)), treeName, node, "statement", null, actor, locaPath, key, text)) return;
            Stats.Statements++;
        }

        private void AddChoices(string treeName, string treeLoca, DS_MultipleChoiceNode node, List<ManifestLine> lines, HashSet<string> seen)
        {
            var choices = node.availableChoices;
            string actor = node.actorName ?? "";
            for (int k = 0; k < choices.Count; k++)
            {
                try
                {
                    var choice = choices[k];
                    var st = choice.statement;
                    string key = st.locaKey;
                    string locaPath = st.useGlobalLoca ? st.GlobalLocaPath : treeLoca;
                    string text = node.GetLocalizedString(st);
                    if (string.IsNullOrEmpty(key) || string.IsNullOrEmpty(text) || text.StartsWith(KeyMissingPrefix, StringComparison.Ordinal))
                    {
                        Stats.SkippedUnused++;
                        continue;
                    }
                    int index = k;
                    if (!TryAdd(lines, seen, LineIdsSafe(() => LineIds.Choice(treeName, locaPath, key, index)), treeName, node, "choice", k, actor, locaPath, key, text)) continue;
                    Stats.Choices++;
                }
                catch (Exception e)
                {
                    LineError(treeName, e);
                }
            }
        }

        private static string? LineIdsSafe(Func<string> build)
        {
            try { return build(); } catch (ArgumentException) { return null; }
        }

        private bool TryAdd(List<ManifestLine> lines, HashSet<string> seen, string? id, string treeName, Node node, string nodeType,
                            int? choiceIndex, string actor, string locaPath, string key, string text)
        {
            if (id == null) { Stats.SkippedInvalid++; return false; }
            if (seen.Contains(id)) { Stats.SkippedDuplicates++; return false; }
            var line = new ManifestLine
            {
                Id = id, Tree = treeName, NodeId = node.ID, NodeType = nodeType, ChoiceIndex = choiceIndex, ActorName = actor,
                Category = LineClassifier.CategoryName(LineClassifier.Classify(treeName, actor)),
                Generic = LineClassifier.IsGenericActor(actor), LocaPath = LineIds.NormalizeLocaPath(locaPath), LocaKey = key, Text = text,
            };
            line.Gvars.AddRange(LineClassifier.ExtractGvars(text));
            var outs = node.outConnections;
            for (int i = 0; i < outs.Count; i++)
            {
                var target = outs[i]?.targetNode;
                if (target != null) line.Next.Add(target.ID);
            }
            var ins = node.inConnections;
            for (int i = 0; i < ins.Count; i++)
            {
                var source = ins[i]?.sourceNode;
                if (source != null) line.Prev.Add(source.ID);
            }
            seen.Add(id);
            lines.Add(line);
            return true;
        }
    }
}
