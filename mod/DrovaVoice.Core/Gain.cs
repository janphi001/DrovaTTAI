using System;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Lautstärke per Sample-Gain (AudioSource.volume endet bei 1,0). Bis einschließlich 100 % rein linear (100 % ist
    /// bit-genau unverändert); darüber begrenzt ein weicher Begrenzer ab dem Knie, damit nichts hart übersteuert.
    /// </summary>
    public static class Gain
    {
        public const int MaxPercent = 200;
        private const float Knee = 0.8f;

        public static int ClampPercent(int percent) => percent < 0 ? 0 : percent > MaxPercent ? MaxPercent : percent;

        public static float Factor(int percent) => ClampPercent(percent) / 100f;

        /// <summary>Weicher Begrenzer: bis zum Knie unverändert, darüber tanh-Kurve mit stetiger Steigung, Ausgabe höchstens ±1.</summary>
        public static float Limit(float y)
        {
            if (float.IsNaN(y)) return 0f;
            float a = Math.Abs(y);
            if (a <= Knee) return y;
            float o = Knee + (1f - Knee) * MathF.Tanh((a - Knee) / (1f - Knee));
            if (o > 1f) o = 1f;
            return y < 0f ? -o : o;
        }

        public static void Apply(float[] samples, int percent)
        {
            float f = Factor(percent);
            if (f == 1f) return;
            if (f < 1f)
            {
                for (int i = 0; i < samples.Length; i++) samples[i] *= f;
                return;
            }
            for (int i = 0; i < samples.Length; i++) samples[i] = Limit(samples[i] * f);
        }
    }
}
