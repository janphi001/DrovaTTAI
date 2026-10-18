namespace DrovaVoice.Core
{
    /// <summary>
    /// Zählt Addressables-Handles eines Katalog-Exports.
    /// <see cref="Discard"/> gibt die aktuelle Variante frei und bleibt offen, <see cref="End"/> schließt.
    /// </summary>
    public sealed class AssetLease
    {
        private int _kept;
        private bool _closed;

        public int Kept => _kept;
        public bool Closed => _closed;

        public bool Keep()
        {
            if (_closed) return false;
            _kept++;
            return true;
        }

        public int Discard()
        {
            int n = _kept;
            _kept = 0;
            return n;
        }

        public int End()
        {
            _closed = true;
            return Discard();
        }
    }
}
