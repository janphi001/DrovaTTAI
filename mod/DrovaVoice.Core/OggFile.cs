using System.IO;

namespace DrovaVoice.Core
{
    /// <summary>
    /// Öffnet eine OGG-Datei zum Lesen, ohne sie auf Windows gegen Umbenennen zu sperren.
    /// <c>File.OpenRead</c> nutzt <c>FileShare.Read</c> und blockiert dort <c>File.Replace</c>,
    /// solange der Decoder die Datei hält. Der Aufrufer schließt den Strom immer selbst,
    /// auch wenn der Decoder beim Öffnen wirft.
    /// </summary>
    public static class OggFile
    {
        public const FileShare ReadShare = FileShare.ReadWrite | FileShare.Delete;

        public static FileStream OpenRead(string path) =>
            new FileStream(path, FileMode.Open, FileAccess.Read, ReadShare);
    }
}
