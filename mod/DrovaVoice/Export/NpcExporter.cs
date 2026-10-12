using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using DrovaVoice.Core;
using Il2CppDrova;
using Il2CppDrova.Sfx.Voices;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Export
{
    public static class NpcExporter
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            WriteIndented = true,
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        };

        public static void Export(string dir, MelonLogger.Instance log)
        {
            Directory.CreateDirectory(dir);
            var npcs = new List<object>();
            foreach (var info in Resources.FindObjectsOfTypeAll<EntityInfo>())
            {
                try
                {
                    npcs.Add(new { entity = info.name, name = info.GetLocalizedName(), locaKey = info.GetLocaKey(), hasPortrait = info.HasPortrait() });
                }
                catch (Exception e) { log.Warning($"EntityInfo {SafeName(info)}: {e.GetType().Name}"); }
            }
            var voices = new List<object>();
            foreach (var map in Resources.FindObjectsOfTypeAll<VoiceMap>())
            {
                try { voices.Add(new { asset = map.name, voiceId = map.GetVoiceID().ToString(), bodyType = map.GetBodyType().ToString() }); }
                catch (Exception e) { log.Warning($"VoiceMap {SafeName(map)}: {e.GetType().Name}"); }
            }
            // Eine leere Liste (z. B. im Hauptmenü ohne geladene Entitäten) darf eine gute Datei nicht überschreiben.
            bool wroteNpcs = WriteIfNotEmpty(Path.Combine(dir, "npcs.json"), npcs, "EntityInfo", log);
            bool wroteVoices = WriteIfNotEmpty(Path.Combine(dir, "voices.json"), voices, "VoiceMap", log);
            log.Msg($"NPC-Export: {npcs.Count} EntityInfo{(wroteNpcs ? "" : " (nicht geschrieben)")}, {voices.Count} VoiceMap{(wroteVoices ? "" : " (nicht geschrieben)")} -> {dir}");
        }

        private static bool WriteIfNotEmpty(string path, List<object> items, string what, MelonLogger.Instance log)
        {
            string? reason = ExportGuard.ShouldWriteList(items.Count);
            if (reason != null)
            {
                log.Warning($"{Path.GetFileName(path)} nicht geschrieben ({what}: {reason}); eine vorhandene Datei bleibt unverändert. Für diesen Export einen Spielstand laden.");
                return false;
            }
            WriteAtomic(path, JsonSerializer.Serialize(items, Options));
            return true;
        }

        private static string SafeName(UnityEngine.Object? o)
        {
            try { return o != null ? o.name : "?"; }
            catch (Exception) { return "?"; }
        }

        /// <summary>Erst in eine .tmp-Datei schreiben, dann ersetzen: nie eine halb geschriebene Ausgabedatei.</summary>
        private static void WriteAtomic(string path, string content)
        {
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, content, new UTF8Encoding(false));
            File.Move(tmp, path, true);
        }
    }
}
