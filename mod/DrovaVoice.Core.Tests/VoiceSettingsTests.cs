using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class VoiceSettingsTests
    {
        [Fact]
        public void ValidValuesPassUnchangedWithoutWarnings()
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 120, 80, "de", 64, false, w);
            Assert.True(s.Enabled);
            Assert.Equal(120, s.DialogPercent);
            Assert.Equal(80, s.PlayerPercent);
            Assert.Equal("de", s.Language);
            Assert.Equal(64, s.CacheMegabytes);
            Assert.Equal(64L * 1024 * 1024, s.CacheBytes);
            Assert.False(s.Diagnostics);
            Assert.Empty(w);
        }

        [Fact]
        public void BarkPercentDefaultsTo100AndIsClamped()
        {
            var w = new List<string>();
            Assert.Equal(100, VoiceSettings.Create(true, 100, 100, "de", 64, false, w).BarkPercent);
            var s = VoiceSettings.Create(true, 100, 100, "de", 64, false, w, barkPercent: 250);
            Assert.Equal(200, s.BarkPercent);
            Assert.Contains("BarkVolume", w[0]);
            Assert.Equal(200, s.PercentFor(VoiceCategory.Bark));
            Assert.Equal(100, s.PercentFor(VoiceCategory.Dialog));
        }

        [Fact]
        public void BarkDistancesHaveDefaultsAndMustBeOrdered()
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, "de", 64, false, w);
            Assert.Equal(15f, s.BarkMinDistance);
            Assert.Equal(120f, s.BarkMaxDistance);
            Assert.Empty(w);
            var bad = VoiceSettings.Create(true, 100, 100, "de", 64, false, w, barkMinDistance: 20f, barkMaxDistance: 10f);
            Assert.Equal(15f, bad.BarkMinDistance);
            Assert.Equal(120f, bad.BarkMaxDistance);
            Assert.Contains("BarkMaxDistance", w[0]);
            var neg = VoiceSettings.Create(true, 100, 100, "de", 64, false, new List<string>(), barkMinDistance: -4f, barkMaxDistance: 12f);
            Assert.Equal(0f, neg.BarkMinDistance);
            Assert.Equal(12f, neg.BarkMaxDistance);
        }

        [Theory]
        [InlineData(-1, 0)]
        [InlineData(250, 200)]
        public void VolumeIsClampedWithWarning(int input, int expected)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, input, input, "de", 64, false, w);
            Assert.Equal(expected, s.DialogPercent);
            Assert.Equal(expected, s.PlayerPercent);
            Assert.Equal(2, w.Count);
            Assert.Contains("DialogVolume", w[0]);
            Assert.Contains("PlayerVolume", w[1]);
        }

        [Theory]
        [InlineData(0, 8)]
        [InlineData(7, 8)]
        [InlineData(100000, 512)]
        public void CacheIsClamped(int input, int expected)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, "de", input, false, w);
            Assert.Equal(expected, s.CacheMegabytes);
            Assert.Single(w);
            Assert.Contains("CacheMB", w[0]);
        }

        [Theory]
        [InlineData(null)]
        [InlineData("")]
        [InlineData("   ")]
        [InlineData("../de")]
        [InlineData("de/en")]
        [InlineData("d e")]
        [InlineData("averyveryverylonglanguage")]
        public void BadLanguageFallsBackToDe(string? input)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, input, 64, false, w);
            Assert.Equal("de", s.Language);
            Assert.Single(w);
            Assert.Contains("AudioLanguage", w[0]);
        }

        [Fact]
        public void LanguageIsTrimmed()
        {
            var s = VoiceSettings.Create(true, 100, 100, " en-GB ", 64, false, new List<string>());
            Assert.Equal("en-GB", s.Language);
        }

        [Fact]
        public void PercentForUsesCategory()
        {
            var s = VoiceSettings.Create(true, 150, 60, "de", 64, true, new List<string>());
            Assert.Equal(150, s.PercentFor(VoiceCategory.Dialog));
            Assert.Equal(60, s.PercentFor(VoiceCategory.Player));
            Assert.True(s.Diagnostics);
        }
    
        [Theory]
        [InlineData(0, 8)]
        [InlineData(200, 512)]
        public void BoundaryValuesPassWithoutWarnings(int percent, int cacheMb)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, percent, percent, "de", cacheMb, false, w);
            Assert.Equal(percent, s.DialogPercent);
            Assert.Equal(cacheMb, s.CacheMegabytes);
            Assert.Empty(w);
        }

        [Theory]
        [InlineData(null)]
        [InlineData("")]
        [InlineData("..")]
        [InlineData("de/..")]
        [InlineData("../de")]
        [InlineData("de/en")]
        [InlineData("d e")]
        [InlineData("averyveryverylonglanguage")]
        public void ExportLanguageUsesTheAudioLanguageFolderRule(string? input)
        {
            var w = new List<string>();
            Assert.Equal("de", VoiceSettings.CleanFolderName(input, "ExportLanguage", w));
            Assert.Contains("ExportLanguage", w[0]);
        }

        [Theory]
        [InlineData("zh_CN", "zh_CN")]
        [InlineData("en-GB", "en-GB")]
        [InlineData(" en ", "en")]
        public void ExportLanguageKeepsAFolderSafeCode(string input, string expected)
        {
            var w = new List<string>();
            Assert.Equal(expected, VoiceSettings.CleanFolderName(input, "ExportLanguage", w));
            Assert.Empty(w);
        }
    }
}
