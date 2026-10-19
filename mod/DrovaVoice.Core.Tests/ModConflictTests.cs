using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ModConflictTests
    {
        [Theory]
        [InlineData("Drova TTS")]
        [InlineData("DrovaTTS")]
        [InlineData("drovatts")]
        [InlineData("drova-tts")]
        [InlineData("Drova_TTS")]
        [InlineData("DrovaTTS, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null")]
        public void RecognizesTheDrovaTtsModAndAssembly(string name) =>
            Assert.True(ModConflict.IsDrovaTtsName(name));

        [Theory]
        [InlineData(null)]
        [InlineData("")]
        [InlineData("DrovaVoice")]
        [InlineData("DrovaTTSMod")]
        [InlineData("Drova_Modding_API")]
        public void IgnoresOtherNames(string? name) =>
            Assert.False(ModConflict.IsDrovaTtsName(name));

        [Fact]
        public void MatchesEitherTheModListOrTheAssembly()
        {
            Assert.True(ModConflict.DrovaTtsLoaded(new[] { "DrovaVoice", "Drova TTS" }, new[] { "DrovaVoice" }));
            Assert.True(ModConflict.DrovaTtsLoaded(new[] { "DrovaVoice" }, new[] { "DrovaTTS" }));
            Assert.False(ModConflict.DrovaTtsLoaded(new[] { "DrovaVoice" }, new[] { "DrovaVoice.Core" }));
            Assert.False(ModConflict.DrovaTtsLoaded(new List<string?>(), new List<string?>()));
        }

        [Fact]
        public void WarningNamesTheConflictAndThatOneModStaysSilent()
        {
            Assert.Contains("DrovaTTS", ModConflict.DrovaTtsWarning);
            Assert.Contains("Dialog-Connector", ModConflict.DrovaTtsWarning);
            Assert.Contains("stumm", ModConflict.DrovaTtsWarning);
        }
    }
}
