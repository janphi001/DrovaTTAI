using System;
using System.Threading;
using System.Threading.Tasks;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class DecodeCacheTests
    {
        private static DecodedClip Sample(float value, long elapsed = 4) =>
            new DecodedClip(new[] { value }, 1, 48000, elapsed);

        [Fact]
        public void TryBeginAdmitsOnlyTheFirstCaller()
        {
            var cache = new DecodeCache();
            Assert.True(cache.TryBegin("a@100"));
            Assert.False(cache.TryBegin("a@100"));
            Assert.Equal(DecodeStatus.Pending, cache.Peek("a@100", out var clip, out var error));
            Assert.Null(clip);
            Assert.Null(error);
        }

        [Fact]
        public void ConcurrentTryBeginHasASingleWinner()
        {
            var cache = new DecodeCache();
            int wins = 0;
            Parallel.For(0, 32, _ =>
            {
                if (cache.TryBegin("shared")) Interlocked.Increment(ref wins);
            });
            Assert.Equal(1, wins);
            Assert.Equal(DecodeStatus.Pending, cache.Peek("shared", out _, out _));
        }

        [Fact]
        public void CompleteThenPeekIsReadyAndTheFirstResultWins()
        {
            var cache = new DecodeCache();
            var first = Sample(0.25f);
            Assert.True(cache.TryBegin("a@100"));
            cache.Complete("a@100", first);
            cache.Complete("a@100", Sample(0.5f));
            cache.Fail("a@100", "spaeter");
            Assert.Equal(DecodeStatus.Ready, cache.Peek("a@100", out var clip, out var error));
            Assert.Same(first, clip);
            Assert.Null(error);
            Assert.Equal(8, clip!.Bytes);
        }

        [Fact]
        public void FailThenPeekIsFailed()
        {
            var cache = new DecodeCache();
            Assert.True(cache.TryBegin("a@100"));
            cache.Fail("a@100", "Datei fehlt");
            Assert.Equal(DecodeStatus.Failed, cache.Peek("a@100", out var clip, out var error));
            Assert.Null(clip);
            Assert.Equal("Datei fehlt", error);
        }

        [Fact]
        public void UnknownKeyIsMissingAndALateCompleteIsIgnored()
        {
            var cache = new DecodeCache();
            Assert.Equal(DecodeStatus.Missing, cache.Peek("nope", out _, out _));
            cache.Complete("nope", Sample(0.1f));
            cache.Fail("nope", "weg");
            Assert.Equal(DecodeStatus.Missing, cache.Peek("nope", out _, out _));
            Assert.Equal(DecodeStatus.Missing, cache.Wait("nope", TimeSpan.Zero, out _, out _));
        }

        [Fact]
        public void WaitOnAReadyKeyDoesNotTimeOut()
        {
            var cache = new DecodeCache();
            var ready = Sample(0.3f, 9);
            Assert.True(cache.TryBegin("a@100"));
            cache.Complete("a@100", ready);
            Assert.Equal(DecodeStatus.Ready, cache.Wait("a@100", TimeSpan.Zero, out var clip, out var error));
            Assert.Same(ready, clip);
            Assert.Null(error);
            Assert.Equal(9, clip!.ElapsedMilliseconds);
        }

        [Fact]
        public void WaitFailsAPendingKeyWhenTheTimeoutElapses()
        {
            var cache = new DecodeCache();
            Assert.True(cache.TryBegin("a@100"));
            Assert.Equal(DecodeStatus.Failed, cache.Wait("a@100", TimeSpan.Zero, out var clip, out var error));
            Assert.Null(clip);
            Assert.Equal(DecodeCache.TimeoutError, error);
            cache.Complete("a@100", Sample(0.2f));
            Assert.Equal(DecodeStatus.Failed, cache.Peek("a@100", out _, out var still));
            Assert.Equal(DecodeCache.TimeoutError, still);
        }

        [Fact]
        public void WaitObservesAResultPublishedFromAnotherThread()
        {
            var cache = new DecodeCache();
            Assert.True(cache.TryBegin("a@100"));
            var payload = Sample(-0.5f, 12);
            using var started = new ManualResetEventSlim(false);
            DecodeStatus status = DecodeStatus.Missing;
            DecodedClip? found = null;
            var waiter = new Thread(() =>
            {
                started.Set();
                status = cache.Wait("a@100", TimeSpan.FromSeconds(2), out found, out _);
            });
            waiter.IsBackground = true;
            waiter.Start();
            Assert.True(started.Wait(TimeSpan.FromSeconds(2)));
            cache.Complete("a@100", payload);
            Assert.True(waiter.Join(TimeSpan.FromSeconds(2)));
            Assert.Equal(DecodeStatus.Ready, status);
            Assert.Same(payload, found);
        }

        [Fact]
        public void TryRemoveDropsAFinishedEntryAndRefusesAPendingOne()
        {
            var cache = new DecodeCache();
            Assert.True(cache.TryBegin("a@100"));
            Assert.False(cache.TryRemove("a@100", out _, out _));
            Assert.Equal(DecodeStatus.Pending, cache.Peek("a@100", out _, out _));
            var payload = Sample(0.7f);
            cache.Complete("a@100", payload);
            Assert.True(cache.TryRemove("a@100", out var clip, out var error));
            Assert.Same(payload, clip);
            Assert.Null(error);
            Assert.Equal(DecodeStatus.Missing, cache.Peek("a@100", out _, out _));
            Assert.True(cache.TryBegin("a@100"));
        }

        [Fact]
        public void RejectsEmptyKeysNullClipsAndANegativeTimeout()
        {
            var cache = new DecodeCache();
            Assert.Throws<ArgumentException>(() => cache.TryBegin(""));
            Assert.Throws<ArgumentException>(() => cache.Peek(null!, out _, out _));
            Assert.Throws<ArgumentNullException>(() => cache.Complete("a@100", null!));
            Assert.Throws<ArgumentException>(() => cache.Fail("a@100", ""));
            Assert.True(cache.TryBegin("a@100"));
            Assert.Throws<ArgumentOutOfRangeException>(() => cache.Wait("a@100", TimeSpan.FromMilliseconds(-1), out _, out _));
        }

        [Fact]
        public void DecodedClipRejectsUnusablePcm()
        {
            Assert.Throws<ArgumentNullException>(() => new DecodedClip(null!, 1, 48000, 0));
            Assert.Throws<ArgumentOutOfRangeException>(() => new DecodedClip(new[] { 0.1f }, 0, 48000, 0));
            Assert.Throws<ArgumentOutOfRangeException>(() => new DecodedClip(new[] { 0.1f }, 1, 0, 0));
            Assert.Throws<ArgumentOutOfRangeException>(() => new DecodedClip(new[] { 0.1f }, 1, 48000, -1));
        }
    }
}
