using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class LineClassifierTests
    {
        [Theory]
        [InlineData("NPC", true)]
        [InlineData("npc", true)]
        [InlineData("TEACHER", true)]
        [InlineData("Participant", true)]
        [InlineData("INSTIGATOR", true)]
        [InlineData("DRUID", true)]
        [InlineData("ACTOR", true)]
        [InlineData("Testfrau", false)]
        [InlineData("", false)]
        [InlineData(null, false)]
        public void Generic_actors_are_recognised_by_exact_name(string? name, bool expected)
            => Assert.Equal(expected, LineClassifier.IsGenericActor(name));

        [Theory]
        [InlineData("Player", true)]
        [InlineData("player", true)]
        [InlineData("Testfrau", false)]
        [InlineData(null, false)]
        public void Player_actor_is_recognised(string? name, bool expected)
            => Assert.Equal(expected, LineClassifier.IsPlayerActor(name));

        [Theory]
        [InlineData("DT_World_Test_Market", true)]
        [InlineData("DT_Generic_Combat_Bandit", true)]
        [InlineData("DT_Comment_Smith", true)]
        [InlineData("DT_Quest_X_WorldDialogue", true)]
        [InlineData("DT_Quest_X_WorldDialogues", true)]
        [InlineData("DT_Main_NPC_Test", false)]
        [InlineData("DT_Main_NPC_Test_Worldly", false)]
        [InlineData("", false)]
        [InlineData(null, false)]
        public void Bark_trees_follow_the_naming_rules(string? tree, bool expected)
            => Assert.Equal(expected, LineClassifier.IsBarkTree(tree));

        [Theory]
        [InlineData("DT_Main_NPC_Test", "Testfrau", LineCategory.Dialog)]
        [InlineData("DT_Main_NPC_Test", "Player", LineCategory.Player)]
        [InlineData("DT_World_Test_Market", "Testfrau", LineCategory.Bark)]
        [InlineData("DT_World_Test_Market", "Player", LineCategory.Player)]
        [InlineData("DT_Generic_Combat_Bandit", "NPC", LineCategory.Bark)]
        public void Classify_puts_the_player_first_then_barks(string tree, string actor, LineCategory expected)
            => Assert.Equal(expected, LineClassifier.Classify(tree, actor));

        [Fact]
        public void Category_names_are_lowercase()
        {
            Assert.Equal("dialog", LineClassifier.CategoryName(LineCategory.Dialog));
            Assert.Equal("player", LineClassifier.CategoryName(LineCategory.Player));
            Assert.Equal("bark", LineClassifier.CategoryName(LineCategory.Bark));
            Assert.Equal("letter", LineClassifier.CategoryName(LineCategory.Letter));
        }

        [Fact]
        public void Gvars_are_listed_in_order_without_duplicates()
        {
            var found = LineClassifier.ExtractGvars("Hallo $GVAR:EVars_Player.Name$, du hast $GVAR:EVars_Test.Gold$ und $GVAR:EVars_Player.Name$.");
            Assert.Equal(new List<string> { "EVars_Player.Name", "EVars_Test.Gold" }, found);
            Assert.Empty(LineClassifier.ExtractGvars("Kein Platzhalter hier."));
            Assert.Empty(LineClassifier.ExtractGvars(null));
        }
    }
}
