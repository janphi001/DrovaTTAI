namespace DrovaVoice.Core
{
    /// <summary>Was die Mod über die sprechende Figur weiß: Geschlecht (m/w, falls bekannt) und ein stabiler Schlüssel (falls vorhanden).</summary>
    public sealed record FigureInfo(char? Gender, string? Key);
}
