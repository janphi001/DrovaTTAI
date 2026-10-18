# Audioformat (Vertrag zwischen Generator und Mod)

Der Generator schreibt nach `<Spiel>/Mods/DrovaVoice/Audio/<Sprache>/`. Die Mod liest **nur** `index.json` und bildet keine Dateinamen selbst.

## Ordner

```
Audio/de/
├─ index.json
├─ dialog/<sha1(id)[:16]>.ogg      NPC-Dialog
├─ bark/<sha1(id)[:16]>.ogg        Welt-Kommentare (Barks), auch Poolvarianten der Barks
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
    "<treeName>|<locaPath>|<andereKey>":       {"file": "dialog/0123456789abcdef.ogg", "duration": 3.214},
    "<treeName>|<locaPath>|<andereKey>|c2":    {"file": "player/default/…ogg",          "duration": 1.9},
    "<treeName>|<locaPath>|<locaKey>#neutral": {"file": "dialog/…ogg",                   "duration": 2.0}
  },
  "variants": {"<treeName>|<locaPath>|<locaKey>": ["neutral"]}
}
```

- Schlüssel = volle Zeilen-ID nach Spec §4 (Aussage, Auswahloption mit `|c<index>`, optional `#<variante>`); Bildung wie in `DrovaVoice.Core.LineIds` (Testvektoren `tests/vectors/line_ids.json`).
- `file` ist relativ zum Sprachordner, mit `/`. `duration` in Sekunden (gerundet auf Millisekunden).
- `variants` listet je Basis-ID die vorhandenen Varianten; Zeilen ohne Variante stehen nicht darin. Fehlt die gewünschte Variante, gilt die Basis-ID. Eine Basis-ID kann dabei ohne eigenen Eintrag nur über ihre Variante vertont sein (Beispiel oben: `<locaKey>` hat nur `#neutral`).
- Zeilen ohne Eintrag bleiben stumm (Untertitel wie im Original). Zeilen, deren einziger Platzhalter der Spielername (`$GVAR:EVars_Player.Name$`) ist, haben, wenn sich der Name sauber streichen lässt, nur den Eintrag `<Basis-ID>#neutral` (Text ohne den Namen); die Mod spielt diese Variante bevorzugt. Zeilen, in denen der Name nicht streichbar ist (z. B. mitten im Satz; Grund `gvar_name`), und Zeilen mit Quest- oder Geldwerten (`gvar_value`) bleiben stumm. `#arden` wird nicht erzeugt.
- **Poolvarianten:** Zeilen generischer Sprecher (`NPC`, Teacher …) haben keinen Eintrag unter der Basis-ID, nur `<Basis-ID>#vm1`, `#vm2`, …, `#vw1`, … (Tag `v<Geschlecht m|w><Nr ab 1>`, Datei je Stimme). Die Mod wählt zur Laufzeit nach Geschlecht und Figur (`docs/playback.md`).
- Der Generator ergänzt den Index bei jedem `install` (frühere Einträge bleiben, solange ihre Datei existiert). OGG-Dateien, die kein Eintrag mehr nennt, bleiben liegen. `install --prune` löscht sie. `install --dry-run` kopiert nichts, schreibt den Index nicht und listet nur, was ein echter Lauf täte (`würde N kopieren, M Einträge, K verwaist`).

## Lautstärke

- Alle Dateien sind auf −16 LUFS normiert (Sprache), unabhängig von Figur und Emotion; wie laut das im Verhältnis zu Musik und Effekten des Spiels wirkt, lässt sich erst im Spiel beurteilen.
- Deshalb muss die Mod Regler anbieten: Dialog, Spieler, Barks (später Briefe), jeweils in Prozent. Der Bereich geht über 100 % hinaus (Boost, z. B. bis 200 %): `AudioSource.volume` endet bei 1,0, also wird die Verstärkung beim Dekodieren auf die Samples angewendet (mit Begrenzung gegen Übersteuern).
- Der Generator ändert die Dateien dafür nicht; eine andere Zielloudness wäre nur ein neuer `encode`-Lauf (Konstante `LOUDNORM` in `generator/drova_voice/encode.py`).
- Wie die Mod diese Regler umsetzt (Einstellungen, Ablauf, Fehlersuche): `docs/playback.md`.
