using System.Collections.Generic;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class ExportGuardTests
    {
        [Fact]
        public void A_normal_catalog_export_may_be_saved() => Assert.Null(ExportGuard.ShouldSave(1200, false, 300));

        [Fact]
        public void A_loaded_trees_export_without_addresses_may_be_saved() => Assert.Null(ExportGuard.ShouldSave(40, false, null));

        [Fact]
        public void Zero_lines_block_the_save() => Assert.Contains("0 Zeilen", ExportGuard.ShouldSave(0, false, null));

        [Fact]
        public void A_loader_that_gave_up_blocks_the_save_even_with_partial_lines()
            => Assert.Contains("abgebrochen", ExportGuard.ShouldSave(10, true, 300));

        [Fact]
        public void Zero_addresses_block_the_save() => Assert.Contains("0 Baum-Adressen", ExportGuard.ShouldSave(10, false, 0));

        [Fact]
        public void Empty_lists_are_not_written_but_filled_ones_are()
        {
            Assert.NotNull(ExportGuard.ShouldWriteList(0));
            Assert.Null(ExportGuard.ShouldWriteList(3));
        }

        [Theory]
        [InlineData("de", "de", true)]
        [InlineData("DE", "de", true)]
        [InlineData("zh_CN", "zh_cn", true)]
        [InlineData("en", "de", false)]
        [InlineData("", "de", false)]
        [InlineData("de", "", false)]
        public void Language_check_compares_case_insensitively(string current, string pref, bool expected)
            => Assert.Equal(expected, LanguageCheck.Matches(current, pref));

        [Fact]
        public void Node_type_summary_lists_the_top_types_by_count()
        {
            var counts = new Dictionary<string, int> { ["A"] = 2, ["B"] = 9, ["C"] = 5, ["D"] = 1 };
            Assert.Equal("B 9, C 5, +2 weitere Typen", NodeTypeCounts.Summarize(counts, 2));
            Assert.Equal("keine", NodeTypeCounts.Summarize(new Dictionary<string, int>()));
        }
    }
}
