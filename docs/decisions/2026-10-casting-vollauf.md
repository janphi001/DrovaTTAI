# Casting und Vollauf (Plan 5), 2026-10-15

Nur Zahlen und Entscheidungen, keine Spieltexte.

- **Sprecher:** 245 benannte Sprecher haben einen Steckbrief (162 m, 83 w; Alter überwiegend `mittel`). 117 Steckbriefe hatten Konfidenz unter 0,6; die Hörstufe war die Gegenprobe. Femke ist ein Mann (von Hand gesetzt). Der LLM markierte 30 Sprecher als `schurke`; davon blieben 3 (Aldrik, Boris, Laurin), 27 wurden von Hand auf „kein Typ“ gesetzt, weil sonst gewöhnliche Händler auf der einen hellen Schurkenvariante gelandet wären.
- **Zuteilung:** deterministisch (`cast --propose`), Typ-Varianten für gewöhnliche Figuren hart bestraft (`W_TYPE_EXTRA = 30`). Nach der Hörstufe von Hand geändert: Jola `emma`, Meluna `valentina`, Reija `lebhafte_junge_frau_37bab8` (`casting/casting.yaml`). Rest steht in `casting/casting_auto.yaml`. Einzige Notbesetzung: ein Ferkel-Sprecher ohne Kinderstimme.
- **Emotionen:** 4.975 LLM-Zeilen und 642 Regel-Zeilen (`casting/emotions.jsonl`) für 1.341 Dialogbäume.
- **Vollauf bei Fish (Modell `s2.1-pro-free`):** 9 Etappen à rund 100.000 Zeichen, **858.170 Zeichen insgesamt** (Hörstufe 17.756 inklusive). Etappe 6 brach einmal mit HTTP 503 (Dienst nicht erreichbar) ab; der erneute Lauf holte alles aus dem Cache nach. Weder Limit noch Guthabenfehler. Im Spielordner liegen 11.413 Einträge (506 MB OGG). `report --by-speaker`: **Lücken: 0**; nicht vertont sind nur die erwarteten Gründe (`gvar` 395, `unspeakable`, `player_choice` 6.491) und die generischen Sprecher ohne Stimme (`no_voice` 205 Dialogzeilen, 153 Barks).
- **Nicht Teil von Plan 5:** generische Sprecher (`NPC`, `Teacher`, `Druid`, `Actor`, `Participant`), Barks, Briefe, Namensvarianten, Regler.
- **Offen:** Stichprobe im Spiel durch den Nutzer; die Wirkung der Varianten (Alte Frau, Riese) im Spiel hören.
