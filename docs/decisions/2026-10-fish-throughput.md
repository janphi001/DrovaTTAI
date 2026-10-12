# Fish-Durchsatzmessung (Plan 2, Task 4), 2026-10-12

- Modell `s2.1-pro-free`, Stimme Lena, sequentiell (eine Anfrage nach der anderen), mit ausdrücklichem Ja des Nutzers.
- Stichprobe: 495 Spielzeilen (`bakeoff select --per-bucket 55`), 37.068 Zeichen.
- **Fehler: 0** (kein HTTP 429, keine Wiederholungen nötig), kein Ratenlimit erreicht.
- Audio 2.169 s, Rechenzeit 1.326 s: **Echtzeitfaktor 0,61** (schneller als Echtzeit).
- Durchsatz: rund 22 Zeilen/Minute, rund 1.680 Zeichen/Minute.
- Hochrechnung 22 h Audio: **rund 13,4 h sequentiell**.

## Parallelität (je 48 Zeilen, ein Worker-Prozess pro Anfragestrang, Stimme Lena)
| Parallel | Wanduhr | Wanduhr/Audio | Fehler |
|---|---|---|---|
| 2 | 24 s | 0,65 | 0 |
| 4 | 12 s | 0,32 | 0 |
| 8 | 8 s | 0,20 | 0 |
| 16 | 5 s | 0,14 | 0 |

Bis 16 gleichzeitige Anfragen gab es keinen Fehler und kein 429; die Grenze ist damit noch nicht gefunden. Kurze Läufe, Anlaufzeit der Worker ist mit eingerechnet. Hochrechnung 22 h Audio: bei 8 parallel rund 4,4 h, bei 16 parallel rund 3 h. Für Plan 3: Standard 8 parallel mit Rückfall bei 429; höhere Werte erst nach einem längeren Lauf freigeben.

## Offen
- Kosten bzw. Tarif: Free-Modell, Limits und Preise für 22 h sind ungeklärt. Frage an den Nutzer, ob der Free-Tarif reicht oder ein bezahlter Tarif in Frage kommt.
- Hörseite: `out/bakeoff/index.html` (Hörtest nimmt der Nutzer ab).
