using System;
using System.Collections.Generic;
using System.Threading;

namespace DrovaVoice.Core
{
    public enum DecodeStatus { Missing, Pending, Ready, Failed }

    /// <summary>
    /// Ein Ergebnis je Schlüssel. Der erste <see cref="TryBegin"/> startet die Dekodierung; weitere Aufrufe warten
    /// oder lesen. <see cref="Complete"/> und <see cref="Fail"/> dürfen von einem anderen Thread kommen.
    /// Der erste Abschluss gewinnt. Ein unbekannter Schlüssel wird ignoriert, damit ein später Worker nicht wirft.
    /// </summary>
    public sealed class DecodeCache
    {
        public const string TimeoutError = "Zeitüberschreitung";

        private readonly object _gate = new object();
        private readonly Dictionary<string, Slot> _slots = new Dictionary<string, Slot>(StringComparer.Ordinal);

        private sealed class Slot
        {
            public DecodeStatus Status = DecodeStatus.Pending;
            public DecodedClip? Clip;
            public string? Error;
            public readonly ManualResetEventSlim Done = new ManualResetEventSlim(false);
        }

        /// <summary>True nur für den ersten Aufrufer. Der startet die Arbeit.</summary>
        public bool TryBegin(string key)
        {
            RequireKey(key);
            lock (_gate)
            {
                if (_slots.ContainsKey(key)) return false;
                _slots.Add(key, new Slot());
                return true;
            }
        }

        public void Complete(string key, DecodedClip clip)
        {
            RequireKey(key);
            if (clip == null) throw new ArgumentNullException(nameof(clip));
            Finish(key, DecodeStatus.Ready, clip, null);
        }

        public void Fail(string key, string error)
        {
            RequireKey(key);
            if (string.IsNullOrEmpty(error)) throw new ArgumentException("Fehlertext fehlt.", nameof(error));
            Finish(key, DecodeStatus.Failed, null, error);
        }

        public DecodeStatus Peek(string key, out DecodedClip? clip, out string? error)
        {
            RequireKey(key);
            lock (_gate)
            {
                if (!_slots.TryGetValue(key, out var slot))
                {
                    clip = null;
                    error = null;
                    return DecodeStatus.Missing;
                }
                clip = slot.Clip;
                error = slot.Error;
                return slot.Status;
            }
        }

        /// <summary>
        /// Wartet, bis der Schlüssel fertig oder fehlgeschlagen ist. Läuft die Zeit ab, solange er noch pending ist,
        /// wird er fehlgeschlagen und spätere Abschlüsse zählen nicht mehr.
        /// </summary>
        public DecodeStatus Wait(string key, TimeSpan timeout, out DecodedClip? clip, out string? error)
        {
            RequireKey(key);
            if (timeout < TimeSpan.Zero) throw new ArgumentOutOfRangeException(nameof(timeout));
            Slot? slot;
            lock (_gate)
            {
                if (!_slots.TryGetValue(key, out slot))
                {
                    clip = null;
                    error = null;
                    return DecodeStatus.Missing;
                }
                if (slot.Status != DecodeStatus.Pending)
                {
                    clip = slot.Clip;
                    error = slot.Error;
                    return slot.Status;
                }
            }
            if (!slot.Done.Wait(timeout))
            {
                lock (_gate)
                {
                    if (slot.Status == DecodeStatus.Pending)
                    {
                        slot.Status = DecodeStatus.Failed;
                        slot.Error = TimeoutError;
                        slot.Done.Set();
                    }
                    clip = slot.Clip;
                    error = slot.Error;
                    return slot.Status;
                }
            }
            lock (_gate)
            {
                clip = slot.Clip;
                error = slot.Error;
                return slot.Status;
            }
        }

        /// <summary>Entfernt ein fertiges oder fehlgeschlagenes Ergebnis. Pending bleibt, ein Wartender soll nicht hängen.</summary>
        public bool TryRemove(string key, out DecodedClip? clip, out string? error)
        {
            RequireKey(key);
            lock (_gate)
            {
                clip = null;
                error = null;
                if (!_slots.TryGetValue(key, out var slot) || slot.Status == DecodeStatus.Pending) return false;
                clip = slot.Clip;
                error = slot.Error;
                _slots.Remove(key);
                slot.Done.Dispose();
                return true;
            }
        }

        private void Finish(string key, DecodeStatus status, DecodedClip? clip, string? error)
        {
            Slot? slot;
            lock (_gate)
            {
                if (!_slots.TryGetValue(key, out slot) || slot.Status != DecodeStatus.Pending) return;
                slot.Status = status;
                slot.Clip = clip;
                slot.Error = error;
                slot.Done.Set();
            }
        }

        private static void RequireKey(string key)
        {
            if (string.IsNullOrEmpty(key)) throw new ArgumentException("Schlüssel fehlt.", nameof(key));
        }
    }
}
