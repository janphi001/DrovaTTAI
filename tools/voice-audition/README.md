# Stimmenauswahl für Fish (einmalige Hilfsskripte, Stand 2026-10-12)

Diese Skripte haben die Hörseiten `out/fish_voices/` und `out/fish_voices2/` erzeugt (nicht im Git, enthalten Audio). Sie sind Explorationswerkzeuge, keine Pipeline; die Umsetzung als Generator-Schritt kommt in Plan 3.

- `pick.py`, `pick2.py`: Kandidaten aus der Bibliotheksliste `out/fish_de_library.json` auswählen (Imitationen realer Personen und Figuren per Filter ausschließen).
- `render_candidates.py`, `round2.py`: je Stimme zwei erfundene Testzeilen über den Fish-Worker erzeugen, Tonhöhe messen (Autokorrelation), Varianten per ffmpeg/rubberband bauen.
- `page.py`, `page2.py`: Hörseite mit ✔/✘ und „Auswahl anzeigen“ bauen. Hinweis: kein Backslash-Zeilenumbruch in JS-Strings schreiben (`String.fromCharCode(10)` nutzen).
- `game.ps1`: Spiel starten und das Fenster nach vorn holen (Unity pausiert `Update` im Hintergrund).

Der Fish-Schlüssel kommt nur aus der Umgebungsvariable `FISH_API_KEY`, nie aus den Skripten. Pfade sind relativ zur Repo-Wurzel; Aufruf mit dem Python aus `generator/.venv`.
