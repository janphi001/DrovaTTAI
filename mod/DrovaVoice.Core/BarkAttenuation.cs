namespace DrovaVoice.Core
{
    /// <summary>Lautstärkefaktor (0 bis 1) eines Barks nach dem Abstand zum Spieler: voll bis <c>min</c>, linear bis 0 bei <c>max</c>.</summary>
    public static class BarkAttenuation
    {
        public static float Gain(float distance, float min, float max)
        {
            // NaN-Lautstärke an der AudioSource würde jeden Frame in den Mixer laufen. Ungültige Grenzen: hörbar lassen.
            if (float.IsNaN(distance) || !float.IsFinite(min) || !float.IsFinite(max)) return 1f;
            if (distance <= min) return 1f;
            if (!(max > min) || distance >= max) return 0f;
            float gain = 1f - (distance - min) / (max - min);
            if (gain <= 0f) return 0f;
            if (gain >= 1f) return 1f;
            return gain;
        }
    }
}
