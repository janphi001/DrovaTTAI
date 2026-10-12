# Fish-Durchsatzmessung (Plan 2, Task 4), 2026-10-12

- Modell `s2.1-pro-free`, Stimme Lena, sequentiell (eine Anfrage nach der anderen), mit ausdrücklichem Ja des Nutzers.
- Stichprobe: 495 Spielzeilen (`bakeoff select --per-bucket 55`), 37.068 Zeichen.
- **Fehler: 0** (kein HTTP 429, keine Wiederholungen nötig), kein Ratenlimit erreicht.
- Audio 2.169 s, Rechenzeit 1.326 s: **Echtzeitfaktor 0,61** (schneller als Echtzeit).
- Durchsatz: rund 22 Zeilen/Minute, rund 1.680 Zeichen/Minute.
- Hochrechnung 22 h Audio: **rund 13,4 h sequentiell**.

## Offen
- Parallelität nicht gemessen; ein Test mit 2-4 gleichzeitigen Anfragen zeigt, ob Fish mehr zulässt und wo 429 beginnt.
- Kosten bzw. Tarif: Free-Modell, Limits und Preise für 22 h sind ungeklärt. Frage an den Nutzer, ob der Free-Tarif reicht oder ein bezahlter Tarif in Frage kommt.
- Hörseite: `out/bakeoff/index.html` (Hörtest nimmt der Nutzer ab).
