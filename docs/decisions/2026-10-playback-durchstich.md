# Durchstich Wiedergabe in der Mod (Plan 4), 2026-10-15

Nur Namen, Zahlen und Entscheidungen, keine Spieltexte.

## Ergebnis
- **Abgenommen vom Nutzer:** Enya, Femke, Gerion und Gilwar sind im Spiel hörbar, die Untertitel laufen synchron, die Lautstärke bei 100 % passt, die Stimmen klingen mit Emotionen gut („klingt gut“).
- Adela und Jero kamen im Spieltest nicht vor (Jero führt das Ruinenlager, also Mittelspiel; Adela ließ sich nicht verorten). Statt ihrer wurden die Figuren in der Nähe des Nutzers vertont.
- Log: Index mit 433 Zeilen geladen, Connector der Modding API ersetzt (erst in der Welt), Zeilen laden in 6–43 ms, keine Fehler der Mod.

## Beantwortete Risiken
- **P1/R-AudioManager:** `AudioManager` scheitert im Hauptmenü (`WorldEventSystemManager.Instance` ist `null`); Ersetzen erst, wenn die Instanz existiert, funktioniert.
- **P3 (IDs):** Die zur Laufzeit gebildeten Zeilen-IDs treffen den Index.
- **P2 (Hauptthread):** Synchrones Dekodieren (6–43 ms je Zeile) verursacht keine merklichen Ruckler.
- **R5:** Überspringen einer Zeile beendet die Stimme sofort. Esc tut im Dialog nichts (Spielverhalten, kein Fehler der Mod).
- **P4/P5:** Das Spiel spricht die gewählte Antwortoption nicht (`saySelection` aus bei Enya). Entscheidung des Nutzers: Der Spieler bleibt dort stumm (siehe `2026-10-player-choices-stumm.md`).

## Entscheidungen des Nutzers
- Regler vorerst nur per `MelonPreferences` (Neustart nötig); Menü oder Hotkeys später.
- Femke ist männlich (Stimme `schales_7ef3ea`); die übrigen Stimmen der vier Figuren sind weiter vorläufig (`lena`, `lukas`, `jonas`).
- Emotionen für diese Figuren: 107 NPC-Zeilen von Haiku markiert (alltäglich 33, zornig 24, streng 14, froh 8, traurig 6, nachdenklich 6, überrascht 5, nervös 5, zärtlich 4, begeistert 2).

## Offen
- Adela und Jero im Spiel hören (Mittelspiel bzw. unklar).
- Regler im Spiel, Namensvarianten (`#arden`/`#neutral`), Barks, Briefe.
- Vollauf des Generators (ohne Spieleroptionen etwa ein Drittel kleiner); Fish-Kosten und Tarif ungeklärt.
- Branch `plan-4-playback` (und die Vorgänger) mergen, Historie umschreiben, Lizenz: Entscheidung des Nutzers.
