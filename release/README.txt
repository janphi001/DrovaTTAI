DrovaVoice {version} – Deutsche KI-Sprachausgabe für Drova – Forsaken Kin
==========================================================================

HINWEIS: ALLE STIMMEN DIESER MOD SIND KI-GENERIERT.
Sie wurden mit der Sprachsynthese von Fish Audio (https://fish.audio) erzeugt.
Kein Mensch hat diese Zeilen eingesprochen.

Inoffizielle Fan-Mod. Kostenlos, nicht zum Verkauf.


WAS DIE MOD MACHT
-----------------
Die Figuren sprechen ihre deutschen Dialoge, die Untertitel laufen wie gewohnt mit.
Vertont sind {entries} Zeilen:

  - Dialoge aller benannten Figuren, jede Figur mit fester Stimme
  - Zurufe in der Welt (Barks), die mit der Entfernung leiser werden
  - Zeilen namenloser Figuren (Wache, Arbeiter …): jede Figur bekommt
    eine feste Stimme aus einem kleinen Pool, passend zum Geschlecht

Nicht vertont: deine eigenen Antwortoptionen (wie im Original), Briefe und
Zeilen mit Quest- oder Geldwerten. Zeilen mit deinem Spielernamen werden ohne
den Namen gesprochen.

Nur für die deutsche Spielsprache.
Ein gespeicherter AudioLanguage-Schlüssel hat Vorrang.


VORAUSSETZUNGEN
---------------
  - Drova – Forsaken Kin (Steam, Windows)
  - MelonLoader 0.7.3
    https://github.com/LavaGang/MelonLoader/releases/tag/v0.7.3
  - Drova Modding API 0.5.4
    https://github.com/Drova-Modding/Drova-Modding-API/releases/tag/release-0.5.4
  - ca. 700 MB freier Platz


INSTALLATION
------------
Tipp: Lege vorher eine Kopie deines Spielordners an.
Den Spielordner findest du in Steam: Rechtsklick auf das Spiel > Verwalten >
Lokale Dateien durchsuchen.

1. MelonLoader installieren: MelonLoader.x64.zip (v0.7.3) in den Spielordner
   entpacken, sodass version.dll und der Ordner MelonLoader neben Drova.exe liegen.
2. Modding API installieren: Modding_API.zip (release-0.5.4) ebenfalls in den
   Spielordner entpacken.
3. Spiel einmal bis ins Hauptmenü starten und wieder beenden.
4. Diese Mod installieren: die Ordner "Mods" und "UserLibs" aus diesem ZIP in den
   Spielordner kopieren. Bestehende Ordner zusammenführen, nicht ersetzen.
5. Spiel starten. Fertig.

So sieht es danach aus:

  Drova - Forsaken Kin\
    Mods\DrovaVoice.dll
    Mods\DrovaVoice\Audio\{language}\index.json  (und die Ordner bark, dialog, player)
    UserLibs\DrovaVoice.Core.dll
    UserLibs\NVorbis.dll


EINSTELLUNGEN
-------------
Im Spiel unter Optionen gibt es einen Bereich "DrovaVoice" mit Reglern für:
  - Lautstärke der Dialoge, deiner Spielerzeilen und der Zurufe (0–200 %)
  - Ab welcher Entfernung Zurufe leiser werden und ab wann sie verstummen

Dieselben Werte stehen auch in UserData\MelonPreferences.cfg im Abschnitt
[DrovaVoice]. Dort lässt sich die Sprachausgabe mit Enabled = false ganz abschalten.


DEINSTALLATION
--------------
Diese Dateien und Ordner aus dem Spielordner löschen:
  Mods\DrovaVoice.dll
  Mods\DrovaVoice\
  UserLibs\DrovaVoice.Core.dll
  UserLibs\NVorbis.dll  (nur, wenn keine andere Mod sie braucht)

MelonLoader und die Modding API entfernst du wie in deren Anleitung beschrieben.


BEKANNTE GRENZEN
----------------
  - Das Spiel wurde mit der Mod noch nicht komplett durchgespielt. Die Stimmen
    sind den Figuren anhand der Spieldaten zugeteilt; manche Figuren können mit
    dem falschen Geschlecht oder einer unpassenden Stimme sprechen.
  - Es ist KI: Betonung und Aussprache passen nicht immer, besonders bei
    Eigennamen und sehr kurzen Ausrufen.
  - Nicht zusammen mit einer anderen Sprachausgabe-Mod (z. B. DrovaTTS) nutzen.
    Die Mod schreibt dann eine Warnung ins Log.
  - Nach einem Spiel-Update können neue oder geänderte Zeilen stumm bleiben.


PROBLEME?
---------
Falsche Stimme, falsches Geschlecht oder ein Fehler? Bitte ein Issue auf GitHub
erstellen: https://github.com/janphi001/DrovaTTAI/issues
Am besten mit Figur, Ort im Spiel und dem Log.

Die Mod schreibt ins Log: MelonLoader\Latest.log im Spielordner.
Zeilen mit "DrovaVoice" zeigen, ob die Mod geladen wurde und ob Fehler auftreten.


Rechtliches und Stimmen-Liste: siehe LIZENZEN.txt
