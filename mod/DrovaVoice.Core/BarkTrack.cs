namespace DrovaVoice.Core
{
    /// <summary>Entscheidet, ob ein verfolgter Bark noch derselbe Clip ist. Der Name wird dafür nicht gebraucht.</summary>
    public static class BarkTrack
    {
        public static bool SameClip(int watchedClipId, int currentClipId) => watchedClipId == currentClipId;
    }
}
