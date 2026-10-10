using DrovaVoice.Core;
using MelonLoader;

[assembly: MelonInfo(typeof(DrovaVoice.DrovaVoiceMod), "DrovaVoice", "0.1.0", "janphi001")]
[assembly: MelonGame("Just2D", "Drova")]
[assembly: MelonAdditionalDependencies("Drova_Modding_API")]

namespace DrovaVoice
{
    public sealed class DrovaVoiceMod : MelonMod
    {
        public override void OnInitializeMelon()
        {
            string probe = LineIds.AudioFileName(LineIds.Statement("DT_Main_NPC_Adela", "Dialog/NPC_Adela", "Plh_5"));
            LoggerInstance.Msg($"DrovaVoice {Info.Version} geladen (Core ok: {probe})");
        }
    }
}
