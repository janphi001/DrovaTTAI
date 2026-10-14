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
            try
            {
                var statement = statementNode.statement;
                var tree = statementNode.DLGTree;
                string locaPath = statement.useGlobalLoca ? statement.GlobalLocaPath : tree.LocaPath;
                string id = LineIds.Statement(tree.name, locaPath, statement.locaKey);
                var clip = _service.GetClip(id);
                if (clip != null) statement.audio = clip;
            }
            catch (Exception e) { _service.LogError("OnWorldDialogueStatement", e); }
        }
    }
}
