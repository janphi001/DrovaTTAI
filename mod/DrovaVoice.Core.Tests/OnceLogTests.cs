using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class OnceLogTests
    {
        [Fact]
        public void LogsEachKeyOnce()
        {
            var log = new OnceLog();
            Assert.True(log.ShouldLog("a"));
            Assert.False(log.ShouldLog("a"));
            Assert.True(log.ShouldLog("b"));
        }

        [Fact]
        public void StopsLoggingNewKeysAtTheCap()
        {
            var log = new OnceLog(2);
            Assert.True(log.ShouldLog("a"));
            Assert.True(log.ShouldLog("b"));
            Assert.False(log.ShouldLog("c"));
            Assert.False(log.ShouldLog("a"));
        }

        [Fact]
        public void ClearMakesTheSameKeyLogAgain()
        {
            var log = new OnceLog();
            Assert.True(log.ShouldLog("a"));
            log.Clear();
            Assert.True(log.ShouldLog("a"));
        }
    }
}
