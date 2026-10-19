namespace DrovaVoice.Core
{
    /// <summary>
    /// Größe des float-Puffers für eine OGG-Datei. Die Länge kommt aus dem Header und kann überlaufen,
    /// wenn man <c>TotalSamples * Kanäle</c> in einem <c>long</c> rechnet: das Produkt wird dann eine
    /// kleine positive Zahl, und eine kaputte Datei gilt als kurzer, gültiger Clip.
    /// </summary>
    public static class PcmBuffer
    {
        /// <summary>60 s Stereo bei 48 kHz. Darüber wird nicht dekodiert.</summary>
        public const long MaxFloats = 48000L * 60 * 2;

        /// <summary>Unity-AudioClip nimmt höchstens acht Kanäle. Mehr ist ein kaputter Header.</summary>
        public const int MaxChannels = 8;

        /// <summary>
        /// null = die Datei darf in einen Puffer dieser Länge. Sonst der Grund, warum sie stumm bleibt.
        /// <paramref name="floats"/> ist 0, wenn abgelehnt wird.
        /// </summary>
        public static string? Reject(long totalSamples, int channels, int sampleRate, out int floats)
        {
            floats = 0;
            if (channels < 1 || channels > MaxChannels || sampleRate < 1 || totalSamples < 1)
                return "leere oder ungültige Datei";
            if (totalSamples > MaxFloats / channels)
                return "Datei zu lang";
            floats = (int)(totalSamples * channels);
            return null;
        }

        /// <summary>Schneidet auf eine ganze Frame-Grenze. Ein Restkanal würde <c>SetData</c> scheitern lassen und die ganze Zeile stumm machen.</summary>
        public static int Align(int count, int channels)
        {
            if (channels < 1 || count < 1) return 0;
            return count - count % channels;
        }
    }
}
