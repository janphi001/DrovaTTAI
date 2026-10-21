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
            PatchGuard.Run(() =>
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
                if (clip == null && !_service.HasEntry(id) && !_service.IsPoolLine(id)) _service.Recorder?.Record(statementNode, id, locaPath);
                if (clip != null)
                {
                    // Dialog- und Spielerzeilen spielt die Mod selbst: Mit statement.audio skippt das Spiel nur die Stimme, nicht den Text.
                    var voice = _service.DialogueVoice;
                    if (voice != null && voice.Ready && !(clip.name ?? "").StartsWith(BarkDistance.BarkClipPrefix, System.StringComparison.Ordinal))
                    {
                        voice.Queue(clip);
                        return;
                    }
                    statement.audio = clip;
                    // Der Clip bleibt sonst an der Aussage stehen: Wiederholungen riefen den Connector nicht mehr auf (falsche Figur bei
                    // geteilten Aussagen, neue Lautstärke aus dem Optionsmenü käme nie an). Nach dem Abspielstart wieder freigeben.
                    _service.BarkDistance?.Watch(statement, clip);
                }
            }, e => _service.LogError("OnWorldDialogueStatement", id, e));
        }
    }
}
