namespace DrovaVoice.Core
{
    public enum ProbeDecision { Stay, SwitchToFallback, GiveUp }

    /// <summary>
    /// Outcome-based choice between two load variants: if the first <c>probeSize</c> loads of a variant all fail
    /// (no success yet), switch from the primary to the fallback; if the fallback's first <c>probeSize</c> loads
    /// also all fail, give up. One success locks the current variant for good.
    /// </summary>
    public sealed class VariantProbe
    {
        private readonly int _probeSize;
        private int _attempts;
        private bool _succeeded;

        public VariantProbe(int probeSize) { _probeSize = probeSize; }

        public bool UsingFallback { get; private set; }

        public ProbeDecision OnResult(bool ok)
        {
            if (_succeeded) return ProbeDecision.Stay;
            if (ok) { _succeeded = true; return ProbeDecision.Stay; }
            if (++_attempts < _probeSize) return ProbeDecision.Stay;
            if (UsingFallback) return ProbeDecision.GiveUp;
            UsingFallback = true;
            _attempts = 0;
            return ProbeDecision.SwitchToFallback;
        }
    }
}
