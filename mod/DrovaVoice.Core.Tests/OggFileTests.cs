using System;
using System.IO;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class OggFileTests
    {
        [Fact]
        public void ReadShareIncludesDeleteSoInstallCanReplaceTheFile()
        {
            Assert.True(OggFile.ReadShare.HasFlag(FileShare.ReadWrite));
            Assert.True(OggFile.ReadShare.HasFlag(FileShare.Delete));
        }

        [Fact]
        public void OpenReadHoldsTheFileAndReleasesItOnDispose()
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
                    string replacement = path + ".new";
                    File.WriteAllBytes(replacement, new byte[] { 9 });
                    File.Move(replacement, path, true);
                }
                using var after = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None);
                Assert.Equal(1, after.Length);
            }
            finally
            {
                Directory.Delete(dir, true);
            }
        }
    }
}
