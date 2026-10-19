using System;
using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class PatchGuardTests
    {
        [Fact]
        public void AThrownBodyIsReportedAndDoesNotEscape()
        {
            var seen = new List<string>();
            var thrown = new InvalidOperationException("probe");
            PatchGuard.Run(() => throw thrown, e => seen.Add(e.Message));
            Assert.Equal(new[] { "probe" }, seen);
        }

        [Fact]
        public void AThrowingReportDoesNotEscape()
        {
            PatchGuard.Run(
                () => throw new InvalidOperationException("probe"),
                _ => throw new InvalidOperationException("log"));
        }

        [Fact]
        public void ACleanBodyDoesNotReport()
        {
            int reports = 0;
            bool ran = false;
            PatchGuard.Run(() => ran = true, _ => reports++);
            Assert.True(ran);
            Assert.Equal(0, reports);
        }
    }
}
