namespace DrovaVoice.Core
{
    /// <summary>Lautstärkefaktor (0 bis 1) eines Barks nach dem Abstand zum Spieler: voll bis <c>min</c>, linear bis 0 bei <c>max</c>.</summary>
    public static class BarkAttenuation
    {
        public static float Gain(float distance, float min, float max)
        {
            if (float.IsNaN(distance) || distance <= min) return 1f;   // ungültig oder nah: hörbar lassen
            if (distance >= max) return 0f;
            return 1f - (distance - min) / (max - min);
        }
    }
}
