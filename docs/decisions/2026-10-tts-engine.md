# Entscheidung: TTS-Engine und Stimmen-Quelle

Datum: 2026-10-10
Getestet: Kitten TTS 2 (eingebaute Stimme German + Klon), Chatterbox Multilingual (Standard + Klon), XTTS-v2 (3 Sprecher). 36 Zeilen je Stimme (9 Kategorien à 4 Zeilen), dazu ein gezielter Emotionstest mit einem erfundenen Satz.

| Kriterium | Kitten | Chatterbox | XTTS |
|---|---|---|---|
| Deutsch natürlich | Klon mit Viktor Eka klingt insgesamt am besten (Nutzerurteil) | nicht ausdrücklich bewertet | nicht ausdrücklich bewertet |
| Emotionen | kleiner, hörbarer Unterschied, nicht entscheidend; Laut-Tags (`<sigh>`, `<laugh>`) werden auf Deutsch vorgelesen | nicht ausdrücklich bewertet | keine Emotionssteuerung im Rendering |
| Kurze Zeilen | keine Artefakte gemeldet | nicht ausdrücklich bewertet | nicht ausdrücklich bewertet |
| Klonqualität | Referenz xtts-viktor-eka am besten | nicht ausdrücklich bewertet | (liefert die Referenzen) |
| Echtzeitfaktor | 1,46 (eingebaut), 1,36 / 1,33 (Klon) | 0,89 (Standard), 1,03 / 1,04 (Klon) | 0,34 – 0,38 |
| Hochrechnung 22 h Audio | ca. 32 h / 30 h / 29 h | ca. 20 h / 23 h / 23 h | ca. 7,4 – 8,5 h |

Messwerte auf RTX 3080 (10 GB), CUDA, torch 2.6.0+cu124, mit Aufwärmzeile je Worker. Chatterbox enthält die Wasserzeichen-Berechnung (läuft auf der CPU).

**Gewählte Engine (Stand nach dem lokalen Hörtest, später geändert, siehe Nachtrag unten):** Kitten TTS 2 mit geklonten Referenzstimmen (Nutzerentscheidung nach dem Hörtest). Kitten bleibt als lokale Rückfallebene.

**Stimmen-Quelle für den Pool:** Referenzaufnahmen. Erste Referenz: XTTS-Sprecher "Viktor Eka" (`voices/bakeoff/xtts-viktor-eka.wav`, Text `.txt` daneben). Zusätzlich Aufnahmen von Freunden nach `docs/stimmaufnahme.md` (mit Einverständnis, nur privat genutzt).

**Begründung:** Kitten klingt mit der geklonten Referenz am besten. Es ist die langsamste Variante (ca. 30 h Rechenzeit für 22 h Audio), das ist für mehrere Nächte Generierung im Hintergrund vertretbar. XTTS bleibt die schnelle Rückfallebene (ca. 7,5 h), Chatterbox liegt dazwischen.

**Folgen für Plan 2:**
- Kitten bekommt nur Emotions-Prefix (`[emotion]`) und Betonung (`(((Wort)))`); **keine Laut-Tags** (werden vorgelesen). Der Emotionsunterschied ist klein, Szenen-Emotion muss daher vor allem über die Stimmenwahl und ggf. Referenzen mit passender Stimmung kommen.
- Jede Referenz braucht den exakt gesprochenen Text (`ref.txt`) neben der WAV; ohne ihn lädt Kitten Whisper (ca. 3 GB, nur Englisch). Der Stimmen-Pool in Spec §6 muss `ref.txt` aufnehmen.
- Modellversionen festlegen (Hugging-Face-Revision, Paketversionen per `uv pip freeze`) und im Handshake melden; der Cache-Schlüssel "Modellversion" (Spec §6) braucht das. Kitten lädt außerdem den Codec `ResembleAI/chatterbox-turbo` (ca. 1 GB, MIT).
- Lange Texte satzweise teilen und die Dauer gegen die Textlänge prüfen (Chatterbox kappt bei ca. 40 s, Kitten teilt selbst bei 380 Zeichen).
- Kitten laut README (KittenML/KittenTTS): Mehrsprachig (Deutsch, ca. 10 % des Trainings), Emotionssteuerung ist "early beta" und beeinflusst nur die Sprechweise; die nicht-englischen Stimmen beruhen auf je einem Referenzclip und sind fragiler; für Nicht-Englisch `normalize=False` (so umgesetzt). Zum stärkeren Ausdruck nennt die Doku zusätzlich `preset="expressive"` mit `top_k=0`, `temperature≈1.1`, `top_p≈0.95` (noch nicht getestet).
- Lizenzen: Kitten (Stellon Labs Community License v. 5. Juli 2024, Text am 2026-10-10 gelesen: erlaubt Forschung, nicht-kommerzielle und begrenzte kommerzielle Nutzung; Kopie der Lizenz und Namensnennung nur beim Weitergeben der Modelle/Derivate oder eines Produkts, das sie nutzt; reine private Nutzung ohne Verteilung ist unkritisch). XTTS-Ausgaben unterliegen der CPML (nur nicht-kommerziell). Das gilt auch für Stimmen, die aus XTTS-Referenzen abgeleitet werden; Aufnahmen von Freunden vermeiden das. Nichts davon wird verteilt.
- Offen: 4 Zeilen Emotionen im Hörtest sind eine dünne Basis; das ist durch den Emotionstest (10 Emotionen, ein Satz) ergänzt.

## Nachtrag 2026-10-10 (nach den Fish-Audio-Tests): Engine = Fish Audio (Cloud)

**Entscheidung des Nutzers:** Für die Vertonung wird **Fish Audio** (Modell S2.1 Pro, `https://api.fish.audio/v1/tts`) mit den **offiziellen deutschen Fish-Stimmen** genutzt (Autor "Fish Official": Lena, Leon, Melanie, Lukas (Österreich), Emma, Elin (Schweiz), Jonas, Valentina (Österreich); Nico (Schweiz) und Stefan sind in der API nicht auffindbar). Die Stimmen aus der öffentlichen Bibliothek (m1 "Vorlesen", w1 "Christa" waren gut, die übrigen männlichen nicht) werden nicht verwendet. Die Zuordnung Stimme -> Figur gehört in Plan 2.

**Begründung:** Vom Nutzer nur knapp festgehalten: Von den Fish-Bibliotheksstimmen gefielen m1 ("Vorlesen") und w1 ("Christa"), die übrigen männlichen nicht; die offiziellen Fish-Stimmen werden genommen. Ob Fish bei Emotionen und Aussprache insgesamt besser ist als Kitten, wurde nicht ausdrücklich bewertet. Sachlich spricht für Fish, dass die Emotionssteuerung (`[angry]`, `[sad]`, `[whispering]` als frei formulierte Anweisung, laut Doku für Deutsch, 24 + 25 Emotionen, Laute wie `[laughing]`, `[break]`) dokumentiert ist, während Kittens Emotionen nur schwach wirken und seine Laut-Tags vorgelesen werden.

**Folgen und Randbedingungen (verifiziert am 2026-10-10 gegen docs.fish.audio und fish.audio/terms; keine Rechtsberatung):**
- **Cloud:** Jeder gesprochene Text geht an Fish. Das widerspricht dem bisherigen Spec-Ziel "lokal"; die Spec ist anzupassen. Die Terms erlauben Fish, Inhalte und Nutzungsdaten zur Verbesserung der Modelle zu nutzen; Löschen des Accounts entfernt nur die Sichtbarkeit, Kopien können bleiben. Das betrifft alle Spieltexte.
- **Lizenz:** Die kostenlose Nutzung ist laut Terms auf **persönliche, nicht-kommerzielle** Nutzung beschränkt; kommerzielle Nutzung braucht einen bezahlten Plan. Die Mod verteilt kein Audio (Spec), die Nutzung bleibt privat. Ausgaben nicht als Trainingsdaten für konkurrierende Modelle verwenden; KI-Herkunft nicht verschleiern.
- **Kosten/Limits ungeklärt:** Die Preisseite war nicht abrufbar, Ratenlimits sind nicht dokumentiert. Grobe Menge: 22 h Audio entsprechen etwa 1,2 Mio. Zeichen und, bei 2-5 s Rechenzeit je Zeile, mehreren Stunden sequentiell. Vor dem Vollauf Kosten/Limits klären und mit einem Stichprobenlauf (z. B. 500 Zeilen) messen. "Kostenlos" ist laut Nutzer aktuell der Stand, kann sich ändern; `s2.1-pro-free` ist das Free-Tier-Modell.
- **Key:** Nie ins Repo. Nur aus Umgebungsvariable `FISH_API_KEY` (oder einer ignorierten Datei) lesen. Der Key, der beim Test benutzt wurde, stand im Chat und ist nach dem Test zurückzusetzen.
- **Plan 2:** Neuer Engine-Worker `fish` (gleiches Protokoll wie die anderen, HTTP-Aufruf mit Wiederholung/Backoff, begrenzte Parallelität, Modellname als Cache-Schlüssel statt Hugging-Face-Revision). Emotionen aus `EmotionTag` auf Fish-Klammerbefehle abbilden (`[angry]` usw. am Satzanfang, Laute `[sighing]`, `[laughing]`, `[break]` funktionieren laut Doku). Der Spielername-Platzhalter und GVAR-Texte bleiben wie in Plan 1. Kitten bleibt als lokale Alternative; die Lokalität (Spec) ist als bewusste Abweichung zu dokumentieren.
- **Vergleichstest offen:** `out/fishkitten/index.html` stellt die Fish-Originale neben Kitten-Klone derselben Stimmen (Fallback, falls Fish später wegfällt oder kostenpflichtig wird).
