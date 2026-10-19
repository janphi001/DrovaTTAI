using System;
using System.IO;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class OggFileTests
    {
        [Fact]
        public void ReadShareIncludesDeleteSoPruneCanRemoveTheFile()
        {
            Assert.True(OggFile.ReadShare.HasFlag(FileShare.ReadWrite));
            Assert.True(OggFile.ReadShare.HasFlag(FileShare.Delete));
        }

        [Fact]
        public void OpenReadLetsPruneDeleteTheOpenFile()
        {
            string dir = Path.Combine(Path.GetTempPath(), "ogg-share-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                string path = Path.Combine(dir, "clip.ogg");
                File.WriteAllBytes(path, new byte[] { 1, 2, 3, 4 });
                using (var stream = OggFile.OpenRead(path))
                {
                    Assert.True(stream.CanRead);
                    Assert.Throws<IOException>(() =>
                    {
                        using var blocked = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None);
                    });
                    // Windows erlaubt kein Umbenennen über eine offene Datei, auch nicht mit FileShare.Delete.
                    // Löschen geht: die Datei verschwindet spätestens, wenn der Strom schließt.
                    File.Delete(path);
                }
                Assert.False(File.Exists(path));
            }
            finally
            {
                Directory.Delete(dir, true);
            }
        }
    }
}
