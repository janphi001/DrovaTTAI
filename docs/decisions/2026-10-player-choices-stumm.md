# Spielerauswahl bleibt stumm (2026-10-15)

Nur Zahlen und Entscheidungen, keine Spieltexte.

- Von 6.610 Spielerzeilen sind 6.491 Antwortoptionen und nur 119 Aussagen des Spielers. Im Spieltest (Enya) meldete die Mod `saySelection aus`: Das Spiel spricht die gewählte Option nicht.
- **Entscheidung des Nutzers:** Der Spieler bleibt dort stumm wie im Original. Der Generator überspringt Auswahloptionen (`player_choice`), erzeugt dafür keine Dateien und trägt sie nicht in den Index ein. Die Aussagen des Spielers werden weiter mit `default_player` gesprochen.
- Folge für den Vollauf: rund ein Drittel weniger Zeilen und Kosten.
- Aufgeräumt: 151 verwaiste Optionsdateien aus dem Mod-Ordner entfernt; `index.json` hat 282 Einträge (Adela, Jero, Enya, Femke, Gerion, Gilwar).
- Der Auswahl-Hook in der Mod (`ChoiceHook`, nur bei `saySelection`) bleibt als Reserve bestehen.
