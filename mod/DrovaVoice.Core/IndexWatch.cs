using System;
using System.IO;

namespace DrovaVoice.Core
{
    /// <summary>Länge und Schreibzeit von index.json. Zwei Stände gelten als verschieden, wenn eines davon abweicht.</summary>
    public readonly record struct FileStamp(long Length, long LastWriteUtcTicks);

    public enum IndexWatchAction
    {
        None = 0,
        Missing = 1,
        Load = 2,
    }

    /// <summary><see cref="Log"/> ist wahr, wenn die Mod diesen Schritt ins Log schreiben soll. Stille Versuche loggen nicht noch einmal.</summary>
    public readonly record struct IndexWatchStep(IndexWatchAction Action, bool Log);

    /// <summary>
    /// Entscheidet, wann index.json neu gelesen wird. Die Mod fragt das im Abstand von etwa einer Sekunde
    /// (alle 60 Frames) und zusätzlich, wenn reload.trigger liegt. Geändert heißt: andere Länge oder andere Schreibzeit.
    /// Dieselbe Fehlermeldung kommt einmal pro Schreibstand. Wenige stille Versuche holen eine Datei nach,
    /// die beim ersten Lesen gerade ersetzt wurde (install schreibt erst .tmp und ersetzt dann). Danach bleibt
    /// es ruhig, bis sich der Schreibstand ändert oder reload.trigger liegt.
    /// </summary>
    public sealed class IndexWatch
    {
        public const int DefaultRetryPolls = 5;
        public const int DefaultQuietRetries = 2;
        private readonly int _retryEvery;
        private readonly int _quietRetries;
        private FileStamp? _loaded;
        private FileStamp? _failedStamp;
        private int _pollsSinceFailure;
        private int _failedAttempts;
        private bool _missingNoted;

        public IndexWatch(int retryEvery = DefaultRetryPolls, int quietRetries = DefaultQuietRetries)
        {
            if (retryEvery < 1) throw new ArgumentOutOfRangeException(nameof(retryEvery));
            if (quietRetries < 0) throw new ArgumentOutOfRangeException(nameof(quietRetries));
            _retryEvery = retryEvery;
            _quietRetries = quietRetries;
        }

        public bool HasIndex => _loaded != null;

        public static bool TryReadStamp(string path, out FileStamp stamp)
        {
            stamp = default;
            var info = new FileInfo(path);
            if (!info.Exists) return false;
            stamp = new FileStamp(info.Length, info.LastWriteTimeUtc.Ticks);
            return true;
        }

        public IndexWatchStep Poll(bool exists, FileStamp? stamp, bool force)
        {
            if (!exists)
            {
                bool log = force || !_missingNoted;
                _missingNoted = true;
                return new IndexWatchStep(IndexWatchAction.Missing, log);
            }

            _missingNoted = false;
            bool changed = _loaded is not FileStamp loaded || stamp is null || loaded != stamp.Value;
            bool sameFailure = stamp is FileStamp current && _failedStamp is FileStamp failed && failed == current;

            if (force || (changed && !sameFailure))
            {
                _pollsSinceFailure = 0;
                return new IndexWatchStep(IndexWatchAction.Load, true);
            }

            if (!sameFailure || _failedAttempts > _quietRetries) return new IndexWatchStep(IndexWatchAction.None, false);

            _pollsSinceFailure++;
            if (_pollsSinceFailure < _retryEvery) return new IndexWatchStep(IndexWatchAction.None, false);
            _pollsSinceFailure = 0;
            return new IndexWatchStep(IndexWatchAction.Load, false);
        }

        public void NoteLoaded(FileStamp stamp)
        {
            _loaded = stamp;
            _failedStamp = null;
            _pollsSinceFailure = 0;
            _failedAttempts = 0;
            _missingNoted = false;
        }

        /// <summary>Der letzte Leseversuch für diesen Schreibstand ist fehlgeschlagen. Der bisher geladene Index bleibt.</summary>
        public void NoteFailure(FileStamp? stamp)
        {
            if (_failedStamp is FileStamp previous && stamp is FileStamp next && previous == next) _failedAttempts++;
            else _failedAttempts = 1;
            _failedStamp = stamp;
            _pollsSinceFailure = 0;
        }
    }

    public static class IndexMessages
    {
        public static string FirstLoad(int count, int skipped, int dialogPercent, int playerPercent, int barkPercent, int cacheMegabytes) =>
            $"Index: {count} Zeilen ({skipped} übersprungen), Dialog {dialogPercent} %, Spieler {playerPercent} %, Barks {barkPercent} %, Cache {cacheMegabytes} MB.";

        public static string Reloaded(int count, int skipped) =>
            $"Index neu geladen: {count} Zeilen ({skipped} übersprungen).";

        public static string Missing(string path) =>
            $"Kein index.json unter {path}; Vertonung bleibt aus.";

        public static string MissingKept(string path) =>
            $"index.json fehlt unter {path}; der bisherige Index bleibt.";

        public static string Unusable(Exception error) =>
            $"Index nicht nutzbar, Vertonung bleibt aus: {error.GetType().Name}: {error.Message}";

        public static string ReloadFailed(Exception error) =>
            $"Index nicht neu geladen ({error.GetType().Name}: {error.Message}); der bisherige Index bleibt.";

        public static string Unreadable(Exception error) =>
            $"index.json lässt sich nicht prüfen ({error.GetType().Name}: {error.Message}).";
    }
}
