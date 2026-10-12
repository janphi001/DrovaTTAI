using System.Linq;
using DrovaVoice.Core;
using Xunit;

namespace DrovaVoice.Core.Tests
{
    public class CatalogReaderTests
    {
        private const string Catalog = @"{
          ""m_InternalIds"": [
            ""Assets/Content/Dialogue/DT_Main_NPC_Test.asset"",
            ""Assets/Editor/Resources/TestData/DT_World_Tests_X.asset"",
            ""Assets/Content/Dialogue/DT_Main_NPC_Test.asset"",
            ""Assets/Content/Dialogue/Readme.asset"",
            ""Assets/Content/Dialogue/DT_Quest_Test_WorldDialogues.asset"",
            ""Library/PackageCache/DT_Fremd.asset.bundle"",
            ""{UnityEngine.AddressableAssets.Addressables.RuntimePath}/StandaloneWindows64/x.bundle""
          ],
          ""m_KeyDataString"": ""AAAA""
        }";

        [Fact]
        public void Only_dialogue_tree_assets_outside_the_editor_folder_are_listed_once_in_order()
        {
            var found = CatalogReader.TreeAddresses(Catalog);
            Assert.Equal(new[]
            {
                "Assets/Content/Dialogue/DT_Main_NPC_Test.asset",
                "Assets/Content/Dialogue/DT_Quest_Test_WorldDialogues.asset",
            }, found.ToArray());
        }

        [Fact]
        public void A_catalog_without_internal_ids_yields_nothing_and_broken_json_throws()
        {
            Assert.Empty(CatalogReader.TreeAddresses("{}"));
            Assert.ThrowsAny<System.Text.Json.JsonException>(() => CatalogReader.TreeAddresses("{ kaputt"));
        }
    }
}
