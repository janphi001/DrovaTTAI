using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class VariantProbeTests
    {
        [Fact]
        public void A_success_within_the_probe_locks_the_first_variant_for_good()
        {
            var p = new VariantProbe(3);
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.Equal(ProbeDecision.Stay, p.OnResult(true));
            for (int i = 0; i < 20; i++) Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.False(p.UsingFallback);
        }

        [Fact]
        public void All_probe_loads_failing_switches_once_and_the_fallback_gets_its_own_probe()
        {
            var p = new VariantProbe(3);
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.Equal(ProbeDecision.SwitchToFallback, p.OnResult(false));
            Assert.True(p.UsingFallback);
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.Equal(ProbeDecision.Stay, p.OnResult(true));
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
        }

        [Fact]
        public void A_fallback_without_any_success_in_its_probe_gives_up()
        {
            var p = new VariantProbe(2);
            p.OnResult(false);
            Assert.Equal(ProbeDecision.SwitchToFallback, p.OnResult(false));
            Assert.Equal(ProbeDecision.Stay, p.OnResult(false));
            Assert.Equal(ProbeDecision.GiveUp, p.OnResult(false));
        }
    }
}
