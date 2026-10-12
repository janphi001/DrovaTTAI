using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace DrovaVoice.Core
{
    public enum LineCategory { Dialog, Player, Bark, Letter }

    public static class LineClassifier
    {
        private static readonly string[] GenericActors = { "NPC", "TEACHER", "INSTIGATOR", "DRUID", "Participant", "ACTOR" };
        private static readonly Regex GvarRegex = new Regex(@"\$GVAR:([^$]+)\$", RegexOptions.Compiled);

        public static bool IsGenericActor(string? actorName)
        {
            if (string.IsNullOrEmpty(actorName)) return false;
            foreach (var generic in GenericActors)
                if (string.Equals(generic, actorName, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public static bool IsPlayerActor(string? actorName)
            => !string.IsNullOrEmpty(actorName) && actorName.Contains("Player", StringComparison.OrdinalIgnoreCase);

        public static bool IsBarkTree(string? treeName)
        {
            if (string.IsNullOrEmpty(treeName)) return false;
            return treeName.StartsWith("DT_World", StringComparison.Ordinal)
                || treeName.StartsWith("DT_Generic_Combat_", StringComparison.Ordinal)
                || treeName.StartsWith("DT_Comment_", StringComparison.Ordinal)
                || treeName.EndsWith("_WorldDialogue", StringComparison.Ordinal)
                || treeName.EndsWith("_WorldDialogues", StringComparison.Ordinal);
        }

        public static LineCategory Classify(string? treeName, string? actorName)
        {
            if (IsPlayerActor(actorName)) return LineCategory.Player;
            return IsBarkTree(treeName) ? LineCategory.Bark : LineCategory.Dialog;
        }

        public static string CategoryName(LineCategory category) => category.ToString().ToLowerInvariant();

        public static IReadOnlyList<string> ExtractGvars(string? text)
        {
            var result = new List<string>();
            if (string.IsNullOrEmpty(text)) return result;
            foreach (Match m in GvarRegex.Matches(text))
            {
                var name = m.Groups[1].Value;
                if (!result.Contains(name)) result.Add(name);
            }
            return result;
        }
    }
}
