using System.IO;
using System.Text;
using DrovaVoice.Core;

namespace DrovaVoice.Export
{
    public static class ManifestFile
    {
        /// <summary>Schreibt erst in eine .tmp-Datei und ersetzt dann: nie eine halb geschriebene manifest.json.</summary>
        public static void Save(Manifest manifest, string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, ManifestJson.Serialize(manifest), new UTF8Encoding(false));
            File.Move(tmp, path, true);
        }
    }
}
