# Audioformat (Vertrag zwischen Generator und Mod)

Der Generator schreibt nach `<Spiel>/Mods/DrovaVoice/Audio/<Sprache>/`. Die Mod liest **nur** `index.json` und bildet keine Dateinamen selbst.

## Ordner

```
Audio/de/
├─ index.json
├─ dialog/<sha1(id)[:16]>.ogg      NPC-Dialog
├─ bark/…                          Welt-Kommentare (später)
├─ letter/…                        Briefe (später)
└─ player/default/…                Spielerzeilen (Auswahloptionen); weitere Sets später als player/<set>/
```

Dateien sind OGG Vorbis, **48 kHz**, mono, auf −16 LUFS angeglichen, Stille am Anfang und Ende entfernt.

## index.json

```json
{
  "version": 1,
  "language": "de",
  "entries": {
    "<treeName>|<locaPath>|<locaKey>":        {"file": "dialog/0123456789abcdef.ogg", "duration": 3.214},
    "<treeName>|<locaPath>|<locaKey>|c2":      {"file": "player/default/…ogg",          "duration": 1.9},
    "<treeName>|<locaPath>|<locaKey>#neutral": {"file": "dialog/…ogg",                   "duration": 2.0}
  },
  "variants": {"<treeName>|<locaPath>|<locaKey>": ["arden", "neutral"]}
}
```

- Schlüssel = volle Zeilen-ID nach Spec §4 (Aussage, Auswahloption mit `|c<index>`, optional `#<variante>`); Bildung wie in `DrovaVoice.Core.LineIds` (Testvektoren `tests/vectors/line_ids.json`).
- `file` ist relativ zum Sprachordner, mit `/`. `duration` in Sekunden (gerundet auf Millisekunden).
- `variants` listet je Basis-ID die vorhandenen Varianten; Zeilen ohne Variante stehen nicht darin. Fehlt die gewünschte Variante, gilt die Basis-ID.
- Zeilen ohne Eintrag bleiben stumm (Untertitel wie im Original). Es gibt keine Einträge für Zeilen mit `$GVAR:` im Text, bis die Namensvarianten gebaut sind.
- Der Generator ergänzt den Index bei jedem `install` (frühere Einträge bleiben, solange ihre Datei existiert).

## Lautstärke

- Alle Dateien sind auf −16 LUFS normiert (Sprache), unabhängig von Figur und Emotion; wie laut das im Verhältnis zu Musik und Effekten des Spiels wirkt, lässt sich erst im Spiel beurteilen.
- Deshalb muss die Mod Regler anbieten: Dialog, Spieler (später Barks, Briefe), jeweils in Prozent. Der Bereich geht über 100 % hinaus (Boost, z. B. bis 200 %): `AudioSource.volume` endet bei 1,0, also wird die Verstärkung beim Dekodieren auf die Samples angewendet (mit Begrenzung gegen Übersteuern).
- Der Generator ändert die Dateien dafür nicht; eine andere Zielloudness wäre nur ein neuer `encode`-Lauf (Konstante `LOUDNORM` in `generator/drova_voice/encode.py`).
- Wie die Mod diese Regler umsetzt (Einstellungen, Ablauf, Fehlersuche): `docs/playback.md`.
