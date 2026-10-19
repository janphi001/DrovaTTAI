using System.IO;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Öffnet eine OGG-Datei zum Lesen, ohne andere Leser, Schreiber oder <c>install --prune</c> auszusperren.
    /// Ein Umbenennen über die offene Datei scheitert auf Windows trotzdem; <c>install</c> wiederholt dafür.
    /// Der Aufrufer schließt den Strom immer selbst,
    /// auch wenn der Decoder beim Öffnen wirft.
    /// </summary>
    public static class OggFile
    {
        public const FileShare ReadShare = FileShare.ReadWrite | FileShare.Delete;

        public static FileStream OpenRead(string path) =>
            new FileStream(path, FileMode.Open, FileAccess.Read, ReadShare);
    }
}
