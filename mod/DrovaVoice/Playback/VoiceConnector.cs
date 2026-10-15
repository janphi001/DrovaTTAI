using System;
using DrovaVoice.Core;
using Drova_Modding_API.Systems.Audio;
using Il2CppNodeCanvas.DialogueTrees;

namespace DrovaVoice.Playback
{
    /// <summary>
    /// Ersetzt den Standardconnector der Modding API. Beim Laden eines Baums passiert nichts (kein Vorladen);
    /// der API-Patch ruft OnWorldDialogueStatement bei jeder Aussage, deren audio noch null ist.
    /// </summary>
    internal sealed class VoiceConnector : IAudioConnector
    {
        private readonly VoiceService _service;

        public VoiceConnector(VoiceService service) { _service = service; }

        public void OnDialogueTreeLoaded(DialogueTree dialogueTree) { }

        public void OnWorldDialogueStatement(DS_StatementNode statementNode)
        {
            string? id = null;
            try
            {
                var statement = statementNode.statement;
                var tree = statementNode.DLGTree;
                string locaPath = LineIds.ResolveLocaPath(statement.useGlobalLoca, statement.GlobalLocaPath, tree.LocaPath);
                if (!LineIds.TryStatement(tree.name, locaPath, statement.locaKey, out string built))
                {
                    _service.Diag("bad|" + tree.name + "|" + statement.locaKey, $"[Zeile] keine gültige ID (Baum '{tree.name}', Schlüssel '{statement.locaKey}')");
                    return;
                }
                id = built;
                FigureInfo? figure = null;
                if (_service.ProbeFigures || !_service.HasEntry(id))
                {
                    var snapshot = FigureReader.Read(statementNode);
                    figure = FigureReader.ToInfo(snapshot);
                    if (_service.ProbeFigures)
                        _service.Probe(id + "|" + (snapshot?.Guid ?? "-"),
                            $"[Figur] {id} | zeilenSprecher={statementNode.actorName} | actor={snapshot?.ActorName} | body={snapshot?.BodyType} | voice={snapshot?.VoiceId} | guid={snapshot?.Guid} | entity={snapshot?.EntityKey} | dist={snapshot?.Distance:0.0}");
                }
                var clip = _service.GetClip(id, figure);
                if (clip != null) statement.audio = clip;
            }
            catch (Exception e) { _service.LogError("OnWorldDialogueStatement", id, e); }
        }
    }
}
