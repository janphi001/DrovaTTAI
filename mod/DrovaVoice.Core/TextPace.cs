using System;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Wie viele Zeichen sichtbar sein sollen, damit der Text mit der Stimme endet (wie im Spiel, wenn der Clip an der Aussage hängt).
    /// </summary>
    public static class TextPace
    {
        public static int Visible(int totalCharacters, float elapsedSeconds, float clipSeconds)
        {
            if (totalCharacters <= 0) return 0;
            if (clipSeconds <= 0f || elapsedSeconds >= clipSeconds) return totalCharacters;
            if (elapsedSeconds <= 0f) return 0;
            int visible = (int)Math.Ceiling(totalCharacters * (elapsedSeconds / clipSeconds));
            return Math.Min(totalCharacters, Math.Max(0, visible));
        }
    }
}
