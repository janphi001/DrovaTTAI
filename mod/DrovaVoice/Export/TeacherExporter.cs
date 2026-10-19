using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using DrovaVoice.Core;
using Il2CppDrova;
using Il2CppDrova.JournalSystem;
using Il2CppDrova.Talent;
using Il2CppNodeCanvas.DialogueTrees;
using MelonLoader;
using UnityEngine;

namespace DrovaVoice.Export
{
    /// <summary>
    /// Schreibt teachers.json: welche Figuren etwas lehren. Quellen: Talente (TalentContainer.Teachers),
    /// NPC-Tagebucheinträge mit Lehrerkonfiguration (Attributlehrer) und die Namen der DT_Teach_*-Bäume.
    /// Die Lehrgespräche selbst laufen über allgemeine Bäume mit dem Sprecher „Teacher“; mit dieser Liste
    /// kann der Generator sie in der Stimme der jeweiligen Figur erzeugen.
    /// </summary>
    public static class TeacherExporter
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions
        {
            WriteIndented = true,
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        };

        public static void Export(string dir, MelonLogger.Instance log)
        {
            Directory.CreateDirectory(dir);
            var talents = new List<object>();
            int withTeachers = 0;
            foreach (var talent in Resources.FindObjectsOfTypeAll<TalentContainer>())
            {
                try
                {
                    var teachers = new List<object>();
                    var list = talent.Teachers;
                    if (list != null)
                        for (int i = 0; i < list.Count; i++)
                            if (list[i] != null) teachers.Add(Figure(list[i], log));
                    if (teachers.Count > 0) withTeachers++;
                    talents.Add(new { talent = talent.name, teachers });
                }
                catch (Exception e) { log.Warning($"TalentContainer {SafeName(talent)}: {e.GetType().Name}"); }
            }

            var journal = new List<object>();
            foreach (var topic in Resources.FindObjectsOfTypeAll<NPCJournalTopic>())
            {
                try
                {
                    var config = topic._teacherConfig;
                    if (config == null) continue;
                    var info = topic.EntityInfo;
                    journal.Add(new { topic = topic.name, figure = info != null ? Figure(info, log) : null, teacherConfig = config.name });
                }
                catch (Exception e) { log.Warning($"NPCJournalTopic {SafeName(topic)}: {e.GetType().Name}"); }
            }

            var trees = new SortedSet<string>(StringComparer.Ordinal);
            foreach (var tree in Resources.FindObjectsOfTypeAll<DialogueTree>())
            {
                string name = SafeName(tree);
                if (name.StartsWith("DT_Teach_", StringComparison.Ordinal)) trees.Add(name);
            }

            string? reason = ExportGuard.ShouldWriteList(talents.Count + journal.Count);
            if (reason != null)
            {
                log.Warning($"teachers.json nicht geschrieben ({reason}); eine vorhandene Datei bleibt unverändert.");
                return;
            }
            string path = Path.Combine(dir, "teachers.json");
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, JsonSerializer.Serialize(new { talents, journal, trees }, Options), new UTF8Encoding(false));
            File.Move(tmp, path, true);
            log.Msg($"Lehrer-Export: {talents.Count} Talente ({withTeachers} mit Lehrern), {journal.Count} Tagebuch-Lehrer, {trees.Count} DT_Teach-Bäume -> {path}");
        }

        private static object Figure(EntityInfo info, MelonLogger.Instance log)
        {
            string? name = null;
            try { name = info.GetLocalizedName(); }
            catch (Exception e) { log.Warning($"EntityInfo {SafeName(info)}: Name nicht lesbar ({e.GetType().Name})"); }
            return new { entity = SafeName(info), name };
        }

        private static string SafeName(UnityEngine.Object? o)
        {
            try { return o != null ? o.name : "?"; }
            catch (Exception) { return "?"; }
        }
    }
}
