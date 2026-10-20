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
        /// <summary>Weder Aussagen- noch Auswahl-Knoten: je .NET-Typname (kein Spieltext) die Anzahl.</summary>
        public Dictionary<string, int> IgnoredNodeTypes { get; } = new Dictionary<string, int>();
        public int Trees, TreesFailed, TreesSkipped, Statements, Choices, SkippedUnused, SkippedDuplicates, SkippedInvalid, SkippedErrors, PostfixErrors, AlreadyDeserialized, TreesEmpty;
        public override string ToString()
            => $"Bäume {Trees} (fehlgeschlagen {TreesFailed}, übersprungen {TreesSkipped}, ohne Knoten {TreesEmpty}); Aussagen {Statements}, Optionen {Choices}; "
             + $"ohne Text/unbenutzt {SkippedUnused}, doppelt {SkippedDuplicates}, ungültige ID {SkippedInvalid}, Fehler {SkippedErrors}, Modding-API-Postfix-Fehler ignoriert {PostfixErrors}, bereits deserialisiert {AlreadyDeserialized}; "
             + $"ignorierte Knotentypen: {NodeTypeCounts.Summarize(IgnoredNodeTypes)}";
    }

    public sealed class DialogueExporter
    {
        internal const string KeyMissingPrefix = "[LOCA] Key not found";
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
                    if (ExportTree(tree, manifest.Lines, seen)) Stats.Trees++;
                }
                catch (Exception e)
                {
                    Stats.TreesFailed++;
                    _log.Warning($"Baum {SafeName(tree)} nicht exportiert: {e.GetType().Name}: {e.Message}");
                    if (Stats.TreesFailed == 1) _log.Warning("Erster Fehler im Detail: " + e);
                }
            }
            _log.Msg("Export fertig: " + Stats + $"; Zeilen im Manifest {manifest.Lines.Count}");
            return manifest;
        }

        private static string SafeName(DialogueTree tree)
        {
            try { return tree.name; } catch { return "?"; }
        }

        /// <summary>
        /// Die Modding API hängt einen Postfix (DialogueTreePatch) an Graph.SelfDeserialize; dessen Audio-Initialisierung
        /// kann im Hauptmenü mit einer TypeInitializationException scheitern, nachdem die eigentliche Deserialisierung
        /// schon abgeschlossen ist. Diese Ausnahme ist für den Export unerheblich und wird gezählt statt weitergereicht.
        /// </summary>
        private void EnsureDeserialized(DialogueTree tree)
        {
            // Bereits deserialisierte Bäume nicht erneut anfassen: jeder SelfDeserialize-Aufruf löst den Modding-API-Postfix
            // aus, dessen Fehler dann pro Baum im MainThreadDispatcher des Spiels landen (Log-Flut, Spiel hängt).
            try
            {
                var existing = tree.allNodes;
                if (existing != null && existing.Count > 0) { Stats.AlreadyDeserialized++; return; }
            }
            catch (Exception) { /* nicht lesbar: unten normal deserialisieren */ }
            try { tree.SelfDeserialize(); }
            catch (TypeInitializationException) { Stats.PostfixErrors++; }
            try { tree.DeserializeIfNotDoneYet(true); }
            catch (TypeInitializationException) { Stats.PostfixErrors++; }
        }

        private bool ExportTree(DialogueTree tree, List<ManifestLine> lines, HashSet<string> seen)
        {
            EnsureDeserialized(tree);
            string treeName = tree.name;
            string treeLoca = tree.LocaPath ?? "";
            var nodes = tree.allNodes;
            if (nodes == null || nodes.Count == 0)
            {
                // Nach geschluckter Postfix-Ausnahme oder bei wirklich leerem Baum: nicht als exportiert zählen.
                Stats.TreesEmpty++;
                if (Stats.TreesEmpty <= MaxErrorLogs) _log.Warning($"Baum {treeName} hat nach dem Deserialisieren keine Knoten.");
                return false;
            }
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
                    else CountIgnored(node);
                }
                catch (Exception e)
                {
                    LineError(treeName, e);
                }
            }
            return true;
        }

        private void CountIgnored(Node node)
        {
            string type;
            try { type = node.GetType().Name; } catch (Exception) { type = "?"; }
            Stats.IgnoredNodeTypes[type] = Stats.IgnoredNodeTypes.TryGetValue(type, out int n) ? n + 1 : 1;
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
