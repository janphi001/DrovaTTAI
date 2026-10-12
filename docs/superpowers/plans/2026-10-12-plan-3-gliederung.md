# Plan 3: Gliederung (Entwurf, noch kein ausführbarer Plan)

Ziel: Durchstich mit Adela von Export bis Wiedergabe im Spiel (M2), danach Ausbau auf alle Figuren.

## Eingaben aus Plan 2
- Manifest `data/export/de/manifest-loaded.json` (19.535 Zeilen, 93,55 % Abdeckung), `npcs.json`, `voices.json`.
- `casting/fish_voices.yaml`: 41 Stimmen + 7 Varianten.
- Fish-Messung: 8 parallele Worker als Start, Rückfall bei HTTP 429 (`docs/decisions/2026-10-fish-throughput.md`).

## Generator-Schritte (je ein Unterbefehl, wiederaufnehmbar, Ergebnisse als JSONL)
1. **extract**: Manifest + `.loc` abgleichen; Text für `$GVAR:`-Zeilen aus der `.loc` (Manifest hat Werte schon eingesetzt); Spielername und Platzhalter wie im Hörtest behandeln.
2. **cast**: Zeile -> Stimme. 30 Hauptfiguren (>100 Zeilen) eigene Stimme, Rest stabil nach Name/Geschlecht/Alter; Geschlecht aus `bodyType`/`voiceId` (Kandidat `ActorBodyType`), sonst Schätzung aus Steckbrief; Spielerstimme; Ansagestimme nur für Schilder/Steintafeln; Varianten (Pitch/Formant/Tempo) als eigener Teilschritt.
3. **emote**: Emotions- und Ereignis-Tags je Zeile (Regeln zuerst, LLM nur für Unklares).
4. **synth**: Fish-Worker parallel (8), Wiederaufnahme per Sidecar-Text, 429-Backoff.
5. **encode**: WAV -> OGG, Lautheit angleichen, Dateinamen = Zeilen-ID-Hash.
6. **install**: Dateien + Index in den Mod-Ordner.

## Wiedergabe (Mod, C#)
- Zeile im Spiel anzeigen -> ID bilden -> Datei im Index suchen -> abspielen, sonst stumm wie bisher.
- Unterbrechen beim Überspringen/Schließen, Lautstärke-Regler, Ein/Aus-Schalter.

## Durchstich Adela (Reihenfolge)
Adela-Zeilen extrahieren -> Stimme zuweisen -> synthetisieren -> kodieren -> installieren -> im Spiel anhören (Nutzer nimmt den Hörtest ab).

## Offene Fragen an den Nutzer
- Fish-Tarif/Kosten für ca. 22 h Audio (Free-Modell reicht?).
- Lücke von 6,5 % (1.181 Einträge): Notlösung erst nach dem Durchstich (zuerst ohne LLM: Nachbarzeilen, Textgleichheit, Namen in Routineschlüsseln).
- Fehlende Stimmentypen: Kinder, alte Frauen, helle Männer.
- Lizenz (Empfehlung MIT), Historie umschreiben, Merge von `plan-2-fish-export`.

## Nächster Schritt
Mit Skill `superpowers:writing-plans` daraus einen ausführbaren Plan mit Tasks und Tests machen.
