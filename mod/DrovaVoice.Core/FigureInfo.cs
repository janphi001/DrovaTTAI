namespace DrovaVoice.Core
{
    /// <summary>
    /// Was die Mod über die sprechende Figur weiß: Geschlecht (m/w, falls bekannt), ein stabiler Schlüssel (falls vorhanden)
    /// und der Loca-Schlüssel ihrer EntityInfo (z. B. „Carima“, für die Lehrervarianten #t_carima).
    /// </summary>
    public sealed record FigureInfo(char? Gender, string? Key, string? Speaker = null);
}
