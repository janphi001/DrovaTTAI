# Durchstich Adela und Jero (Plan 3), 2026-10-14

Nur Namen, Zahlen und Entscheidungen, keine Spieltexte.

## Ergebnis
- Adela: 21 Zeilen (15 Adela, 6 Spieler, 1 Zeile mit `$GVAR:` übersprungen), Stimme `melanie`. Jero: 234 Zeilen (160 Jero, 74 Spieler), Stimme `german_wisdom_m_3130ae`. Spieler: `leon`.
- Fish: 0 Fehler, 0 auffällige Dauern; Jero 234 Zeilen in 72 s mit 8 parallelen Anfragen.
- Emotionen: Haiku markierte 7 von 21 (Adela) und 110 von 234 (Jero) Zeilen; Regieanweisungen kamen zusätzlich als `stage`.
- Hörtest durch den Nutzer: "ist gut". Stimmen bleiben vorläufig bestätigt; endgültig entscheidet der Nutzer beim Vollauf.

## Befunde
- Review (Opus, lesend) fand 12 Probleme; behoben in `3136bcc`. Wichtigster Befund für die Mod: Ausgabedateien waren 192 kHz, jetzt 48 kHz mono.
- Der Nutzer kann die Lautstärke im Verhältnis zum Spiel nicht vorab einschätzen: Die Mod braucht Lautstärkeregler (siehe `docs/audio-format.md`, Abschnitt Lautstärke).
- Jero zeigt, dass Bäume vieler Hauptfiguren mehrere Sprecher mischen; ohne Stimme bleiben deren Zeilen im Durchstich stumm (`no_voice`).

## Offen für Plan 4 (Wiedergabe in der Mod)
- Lautstärkeregler mit Boost, Kategorien, Laden bei Bedarf, Verhalten beim Überspringen (R5), Fehlerverhalten ohne Datei.
