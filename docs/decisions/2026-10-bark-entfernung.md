# Entfernung der Barks (2026-10-15)

## Befund
- **Hörtest des Nutzers:** Die Barks (Waffenwarnung, Kampfverlust, Arena) werden im Spiel abgespielt, aber **nicht leiser mit der Entfernung**. Sie starten bei 29 bis 112 Einheiten Abstand (Figur-Probe).
- **Modding API:** `DialogueAudioDistanceManager.Register(AudioSource, Transform)` wird nur im `DSDialogueUGUIPatch.Postfix` aufgerufen (für `DS_DialogueUGUI.localSource`, wenn der Sprecher ein `DS_DialogueActor` ist) und regelt die Lautstärke in `Update` nach der Entfernung zum Spieler (`MinDistance`/`MaxDistance` aus der Konfiguration der API). Ob unsere Quelle dort registriert wird, ist ungeklärt: die `AudioLog`-Meldungen der API stehen nicht im MelonLoader-Log.
- **Quelle des Clips:** Die Audio-Sonde (`StaleAudioProbe`) findet die `AudioSource`, die einen Clip der Mod hält (z. B. `…/Dialogue_<Figur>/DialogueUIController`). Damit ist der Zugriff auf die spielende Quelle, den die Spec für eine eigene Abschwächung verlangt, vorhanden.

## Entscheidung
Die Spec-Bedingung „Entfernung nicht über die API“ ist eingetreten. Eine eigene Abschwächung für Barks ist nötig und machbar, sie ist aber ein eigener Plan (Nachtrag zur Spec): Entfernung zwischen Spieler und Quelle messen, Lautstärke über `AudioSource.volume` zwischen `BarkMinDistance` und `BarkMaxDistance` linear dämpfen (nur Kategorie Bark; Dialoge bleiben unberührt). Zu klären vorher: Gerät die Dämpfung mit dem Distanzmanager der API in Konflikt, falls der doch registriert (Prüfung: Anzahl der registrierten Quellen per Reflection loggen); Werte für Min/Max (Vorschlag 4 und 20 Einheiten, die Barks starten ab ca. 30).
