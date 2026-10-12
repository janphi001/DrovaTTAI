using System.IO;
using System.Text;
using DrovaVoice.Core;

namespace DrovaVoice.Export
{
    public static class ManifestFile
    {
        /// <summary>Vollständiger Export (export-all.trigger, Katalog).</summary>
        public const string FullName = "manifest.json";
        /// <summary>Nur die zurzeit geladenen Bäume (export.trigger / F9); ersetzt nie den vollständigen Export.</summary>
        public const string LoadedName = "manifest-loaded.json";

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
