using System;
using DrovaVoice.Core;
using Il2CppDrova.DialogueNew;
using Il2CppInterop.Runtime;
using Il2CppNodeCanvas.DialogueTrees;
using UnityEngine;

namespace DrovaVoice.Playback
{
    internal sealed record FigureSnapshot(string? ActorName, string? BodyType, string? VoiceId, string? Guid, string? EntityKey, float? Distance);

    /// <summary>Liest die sprechende Figur einer Aussage. Jede Angabe ist einzeln abgesichert; null = nicht lesbar.</summary>
    internal static class FigureReader
    {
        public static FigureSnapshot? Read(DS_StatementNode node)
        {
            try
            {
                var raw = node.finalActor;
                if (raw == null) return null;
                var dialogueActor = raw.TryCast<DS_DialogueActor>();
                if (dialogueActor == null) return new FigureSnapshot(Safe(() => raw.name), null, null, null, null, null);
                var actor = Try(() => dialogueActor.Actor);
                var body = actor == null ? null : Try(() => actor.GetActorGender());
                return new FigureSnapshot(
                    Safe(() => dialogueActor.name),
                    body == null ? null : Safe(() => body._bodyType),
                    body == null ? null : Safe(() => body._voiceId),
                    actor == null ? null : Safe(() => actor.GetGuidComponent()?.GuidString),
                    actor == null ? null : Safe(() => actor.GetEntityInfo()?.GetLocaKey()),
                    Distance(dialogueActor));
            }
            catch (Exception) { return null; }
        }

        /// <summary>Schlüssel vorläufig die GUID; die Probe-Auswertung (docs/decisions/2026-10-bark-figur-probe.md) kann das ändern.</summary>
        public static FigureInfo? ToInfo(FigureSnapshot? s) =>
            s == null ? null : new FigureInfo(PoolVoice.GenderFromBodyType(s.BodyType), s.Guid);

        private static float? Distance(DS_DialogueActor actor)
        {
            try
            {
                var cam = Camera.main;
                return cam == null ? null : Vector3.Distance(cam.transform.position, actor.transform.position);
            }
            catch (Exception) { return null; }
        }

        private static string? Safe(Func<object?> read) { try { return read()?.ToString(); } catch (Exception) { return null; } }
        private static T? Try<T>(Func<T> read) where T : class { try { return read(); } catch (Exception) { return null; } }
    }
}
