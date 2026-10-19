using System;
using System.IO;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class IndexWatchTests
    {
        private static FileStamp Stamp(long length, long ticks) => new FileStamp(length, ticks);

        [Fact]
        public void MissingFileIsLoggedOnceUntilItExists()
        {
            var watch = new IndexWatch(retryEvery: 2);
            var first = watch.Poll(exists: false, stamp: null, force: false);
            Assert.Equal(IndexWatchAction.Missing, first.Action);
            Assert.True(first.Log);
            Assert.False(watch.HasIndex);

            var again = watch.Poll(exists: false, stamp: null, force: false);
            Assert.Equal(IndexWatchAction.Missing, again.Action);
            Assert.False(again.Log);

            var back = watch.Poll(exists: true, stamp: Stamp(3, 10), force: false);
            Assert.Equal(IndexWatchAction.Load, back.Action);
            Assert.True(back.Log);
        }

        [Fact]
        public void UnchangedStampDoesNotReload()
        {
            var watch = new IndexWatch();
            var stamp = Stamp(20, 100);
            Assert.Equal(IndexWatchAction.Load, watch.Poll(true, stamp, false).Action);
            watch.NoteLoaded(stamp);
            Assert.True(watch.HasIndex);

            var quiet = watch.Poll(true, stamp, false);
            Assert.Equal(IndexWatchAction.None, quiet.Action);
            Assert.False(quiet.Log);
        }

        [Fact]
        public void ChangedLengthOrWriteTimeAsksForAReload()
        {
            var watch = new IndexWatch();
            var stamp = Stamp(20, 100);
            watch.NoteLoaded(stamp);

            var longer = watch.Poll(true, Stamp(21, 100), false);
            Assert.Equal(IndexWatchAction.Load, longer.Action);
            Assert.True(longer.Log);

            watch.NoteLoaded(Stamp(21, 100));
            var newer = watch.Poll(true, Stamp(21, 101), false);
            Assert.Equal(IndexWatchAction.Load, newer.Action);
            Assert.True(newer.Log);
        }

        [Fact]
        public void ForceReloadsEvenWhenTheStampMatches()
        {
            var watch = new IndexWatch();
            var stamp = Stamp(4, 8);
            watch.NoteLoaded(stamp);
            var forced = watch.Poll(true, stamp, force: true);
            Assert.Equal(IndexWatchAction.Load, forced.Action);
            Assert.True(forced.Log);
        }

        [Fact]
        public void AFailedStampIsLoggedOnceThenRetriedQuietly()
        {
            var watch = new IndexWatch(retryEvery: 2);
            var stamp = Stamp(9, 50);
            var first = watch.Poll(true, stamp, false);
            Assert.True(first.Log);
            watch.NoteFailure(stamp);
            Assert.False(watch.HasIndex);

            var wait = watch.Poll(true, stamp, false);
            Assert.Equal(IndexWatchAction.None, wait.Action);

            var retry = watch.Poll(true, stamp, false);
            Assert.Equal(IndexWatchAction.Load, retry.Action);
            Assert.False(retry.Log);
        }

        [Fact]
        public void ANewStampAfterFailureIsLoggedAgain()
        {
            var watch = new IndexWatch(retryEvery: 5);
            watch.NoteFailure(Stamp(9, 50));
            var next = watch.Poll(true, Stamp(10, 60), false);
            Assert.Equal(IndexWatchAction.Load, next.Action);
            Assert.True(next.Log);
        }

        [Fact]
        public void FailureKeepsThePreviousIndex()
        {
            var watch = new IndexWatch(retryEvery: 3);
            var good = Stamp(4, 1);
            watch.NoteLoaded(good);
            var bad = Stamp(8, 2);
            Assert.True(watch.Poll(true, bad, false).Log);
            watch.NoteFailure(bad);

            Assert.True(watch.HasIndex);
            var wait = watch.Poll(true, bad, false);
            Assert.Equal(IndexWatchAction.None, wait.Action);
            Assert.False(wait.Log);
        }

        [Fact]
        public void DisappearingFileKeepsTheIndexAndWarnsOnce()
        {
            var watch = new IndexWatch();
            var stamp = Stamp(4, 1);
            watch.NoteLoaded(stamp);

            var gone = watch.Poll(false, null, false);
            Assert.Equal(IndexWatchAction.Missing, gone.Action);
            Assert.True(gone.Log);
            Assert.True(watch.HasIndex);

            var stillGone = watch.Poll(false, null, false);
            Assert.False(stillGone.Log);

            var same = watch.Poll(true, stamp, false);
            Assert.Equal(IndexWatchAction.None, same.Action);
        }

        [Fact]
        public void ForceWhileMissingWarnsAgain()
        {
            var watch = new IndexWatch();
            watch.Poll(false, null, false);
            var forced = watch.Poll(false, null, force: true);
            Assert.Equal(IndexWatchAction.Missing, forced.Action);
            Assert.True(forced.Log);
        }

        [Fact]
        public void SuccessfulLoadClearsTheFailureSoTheSameStampStaysQuiet()
        {
            var watch = new IndexWatch(retryEvery: 1);
            var stamp = Stamp(3, 3);
            watch.Poll(true, stamp, false);
            watch.NoteFailure(stamp);
            watch.NoteLoaded(stamp);
            Assert.Equal(IndexWatchAction.None, watch.Poll(true, stamp, false).Action);
        }

        [Fact]
        public void QuietRetriesStopUntilTheStampChangesOrAReloadIsForced()
        {
            var watch = new IndexWatch(retryEvery: 1, quietRetries: 1);
            var bad = Stamp(9, 50);
            watch.Poll(true, bad, false);
            watch.NoteFailure(bad);
            Assert.False(watch.Poll(true, bad, false).Log);
            watch.NoteFailure(bad);

            Assert.Equal(IndexWatchAction.None, watch.Poll(true, bad, false).Action);

            var forced = watch.Poll(true, bad, force: true);
            Assert.Equal(IndexWatchAction.Load, forced.Action);
            Assert.True(forced.Log);

            var changed = watch.Poll(true, Stamp(10, 51), false);
            Assert.Equal(IndexWatchAction.Load, changed.Action);
            Assert.True(changed.Log);
        }

        [Fact]
        public void RejectsANonPositiveRetryInterval()
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => new IndexWatch(0));
            Assert.Throws<ArgumentOutOfRangeException>(() => new IndexWatch(1, -1));
        }

        [Fact]
        public void ReadStampFollowsLengthAndWriteTime()
        {
            string path = Path.Combine(Path.GetTempPath(), "drova-index-stamp-" + Guid.NewGuid().ToString("N") + ".json");
            try
            {
                File.WriteAllText(path, "a");
                Assert.True(IndexWatch.TryReadStamp(path, out var first));
                Assert.Equal(1, first.Length);

                File.WriteAllText(path, "abcd");
                File.SetLastWriteTimeUtc(path, new DateTime(2026, 10, 18, 0, 0, 0, DateTimeKind.Utc));
                Assert.True(IndexWatch.TryReadStamp(path, out var second));
                Assert.Equal(4, second.Length);
                Assert.NotEqual(first, second);

                File.Delete(path);
                Assert.False(IndexWatch.TryReadStamp(path, out _));
            }
            finally
            {
                if (File.Exists(path)) File.Delete(path);
            }
        }

        [Fact]
        public void MessagesNameTheOutcome()
        {
            Assert.Equal(
                "Index: 2 Zeilen (1 übersprungen), Dialog 100 %, Spieler 90 %, Barks 80 %, Cache 64 MB.",
                IndexMessages.FirstLoad(2, 1, 100, 90, 80, 64));
            Assert.Equal("Index neu geladen: 3 Zeilen (0 übersprungen).", IndexMessages.Reloaded(3, 0));
            Assert.Equal("Kein index.json unter Audio/de/index.json; Vertonung bleibt aus.", IndexMessages.Missing("Audio/de/index.json"));
            Assert.Equal("index.json fehlt unter Audio/de/index.json; der bisherige Index bleibt.", IndexMessages.MissingKept("Audio/de/index.json"));

            var error = new IndexFormatException("Sprache passt nicht");
            Assert.Contains("Index nicht nutzbar, Vertonung bleibt aus: IndexFormatException: Sprache passt nicht", IndexMessages.Unusable(error));
            Assert.Contains("der bisherige Index bleibt", IndexMessages.ReloadFailed(error));
            Assert.Contains("lässt sich nicht prüfen", IndexMessages.Unreadable(error));
        }
    }
}
