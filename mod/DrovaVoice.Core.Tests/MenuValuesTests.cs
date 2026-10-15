using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class MenuValuesTests
    {
        private static VoiceSettings Baseline(List<string>? w = null) =>
            VoiceSettings.Create(true, 100, 90, "de", 64, true, w ?? new List<string>(), 80, 15f, 120f);

        [Fact]
        public void MissingValuesKeepTheBaseline()
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(), w);
            Assert.True(s.Enabled);
            Assert.Equal(100, s.DialogPercent);
            Assert.Equal(90, s.PlayerPercent);
            Assert.Equal(80, s.BarkPercent);
            Assert.Equal(15f, s.BarkMinDistance);
            Assert.Equal(120f, s.BarkMaxDistance);
            Assert.Equal("de", s.Language);
            Assert.True(s.Diagnostics);
            Assert.Equal(64, s.CacheMegabytes);
            Assert.Empty(w);
        }

        [Fact]
        public void MenuValuesWinOverTheBaseline()
        {
            var s = Baseline().WithOverrides(new MenuValues(false, 150, 60, 200, 5f, 40f), new List<string>());
            Assert.False(s.Enabled);
            Assert.Equal(150, s.DialogPercent);
            Assert.Equal(60, s.PlayerPercent);
            Assert.Equal(200, s.BarkPercent);
            Assert.Equal(5f, s.BarkMinDistance);
            Assert.Equal(40f, s.BarkMaxDistance);
        }

        [Fact]
        public void VolumeIsClampedWithAWarning()
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(DialogPercent: 250, BarkPercent: -5), w);
            Assert.Equal(200, s.DialogPercent);
            Assert.Equal(0, s.BarkPercent);
            Assert.Contains(w, m => m.Contains("DialogVolume"));
            Assert.Contains(w, m => m.Contains("BarkVolume"));
        }

        [Theory]
        [InlineData(float.NaN, 40f)]
        [InlineData(10f, float.NaN)]
        [InlineData(-3f, float.PositiveInfinity)]
        public void UnusableRangeFallsBackToTheDefaults(float min, float max)
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(BarkMinDistance: min, BarkMaxDistance: max), w);
            Assert.Equal(VoiceSettings.DefaultBarkMinDistance, s.BarkMinDistance);
            Assert.Equal(VoiceSettings.DefaultBarkMaxDistance, s.BarkMaxDistance);
            Assert.NotEmpty(w);
        }

        [Fact]
        public void OnlyOneRangeValueKeepsTheOtherFromTheBaseline()
        {
            var s = Baseline().WithOverrides(new MenuValues(BarkMaxDistance: 200f), new List<string>());
            Assert.Equal(15f, s.BarkMinDistance);
            Assert.Equal(200f, s.BarkMaxDistance);
        }

        [Fact]
        public void DiffReportsEachKindOfChangeSeparately()
        {
            var a = Baseline();
            Assert.Equal(SettingsChange.None, VoiceSettings.Diff(a, Baseline()));
            Assert.Equal(SettingsChange.Enabled, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(Enabled: false), new List<string>())));
            Assert.Equal(SettingsChange.Volume, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(PlayerPercent: 70), new List<string>())));
            Assert.Equal(SettingsChange.Volume, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(BarkPercent: 120), new List<string>())));
            Assert.Equal(SettingsChange.Range, VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(BarkMinDistance: 10f), new List<string>())));
            Assert.Equal(SettingsChange.Enabled | SettingsChange.Volume | SettingsChange.Range,
                VoiceSettings.Diff(a, a.WithOverrides(new MenuValues(false, 10, null, null, 1f, 50f), new List<string>())));
        }

        [Fact]
        public void OverlappingRangeKeepsTheMinAndPushesTheMaxAboveIt()
        {
            var w = new List<string>();
            var s = Baseline().WithOverrides(new MenuValues(BarkMinDistance: 150f, BarkMaxDistance: 100f), w);
            Assert.Equal(150f, s.BarkMinDistance);
            Assert.Equal(160f, s.BarkMaxDistance);
            Assert.Contains(w, m => m.Contains("BarkMaxDistance"));
        }

        [Fact]
        public void OverlapAtTheUpperLimitStaysInsideTheLimit()
        {
            var s = Baseline().WithOverrides(new MenuValues(BarkMinDistance: 500f, BarkMaxDistance: 100f), new List<string>());
            Assert.Equal(490f, s.BarkMinDistance);
            Assert.Equal(500f, s.BarkMaxDistance);
        }

        [Theory]
        [InlineData(600f)]
        [InlineData(float.PositiveInfinity)]
        public void DistancesAboveTheLimitAreClampedWithAWarning(float max)
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, "de", 64, false, w, 100, 15f, max);
            if (float.IsInfinity(max)) { Assert.Equal(15f, s.BarkMinDistance); Assert.Equal(120f, s.BarkMaxDistance); }
            else Assert.Equal(VoiceSettings.MaxBarkDistance, s.BarkMaxDistance);
            Assert.NotEmpty(w);
        }

        [Fact]
        public void NegativeMinIsClampedToZeroWithAWarning()
        {
            var w = new List<string>();
            var s = VoiceSettings.Create(true, 100, 100, "de", 64, false, w, 100, -4f, 50f);
            Assert.Equal(0f, s.BarkMinDistance);
            Assert.Contains(w, m => m.Contains("BarkMinDistance"));
        }

        [Fact]
        public void KeysAreDistinctAndPrefixed()
        {
            var keys = new[] { MenuKeys.Enabled, MenuKeys.DialogVolume, MenuKeys.PlayerVolume, MenuKeys.BarkVolume, MenuKeys.BarkMinDistance, MenuKeys.BarkMaxDistance };
            Assert.Equal(keys.Length, new HashSet<string>(keys).Count);
            Assert.All(keys, k => Assert.StartsWith("DrovaVoice_", k));
        }
    }
}
