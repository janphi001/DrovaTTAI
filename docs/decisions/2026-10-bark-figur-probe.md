# Figur-Probe für Barks (2026-10-15)

Probe: `BarkProbe = true`, Waffenwarnung (`CrimeWarning_HoldingWeapon`) und Kampfverlust (`PlayerLoseFight`) bei sechs Figuren ausgelöst. Die Mod loggt je Aussage `[Figur]` (Name, Körpertyp, VoiceID, GUID, Entity, Entfernung zur Kamera).

## Befund
- **Der Hook liefert die Figur.** `statementNode.finalActor` → `DS_DialogueActor` → `Actor` gibt Name, `ActorBodyType` (`_bodyType`, `_voiceId`), `GuidComponent.GuidString` und `EntityInfo` her. Im Export steht als Sprecher nur `NPC`; die Figur (Dalin, Bruna, Wache …) kennt erst die Laufzeit.
- **Körpertyp ↔ Geschlecht:** `Petite` = weibliche Figuren (Dalin, Bruna, Minira; VoiceID Laureen/Marlies), `Strong` = männliche (Jesko, Zoltan, Wache; VoiceID Dietmar/Thomas/Julian). 6 von 6 stimmig mit den Namen und VoiceIDs. Zuordnung `Strong→m`, `Petite→w` gilt (`PoolVoice.GenderFromBodyType`).
- **GUID:** je Figur verschieden (6 verschiedene Werte). Die `VoiceID` ist dagegen ein Stimmtyp, kein Figurschlüssel (Laureen bei Dalin und Minira). `entity` ist für Wachen nicht eindeutig (`Guard`).
- **Entfernung:** Barks laufen auch aus großer Entfernung an (28,7 bis 111,9 Einheiten bei diesen sechs Fällen). Das bleibt für Task 7 (Abschwächung mit der Entfernung) wichtig.

## Entscheidung
Figurschlüssel = **GUID**, Geschlecht aus dem Körpertyp (`Strong→m`, `Petite→w`). Das ist der bisherige Standard in `FigureReader.ToInfo`; es ändert sich nichts am Code.

## Offen
- **Stabilität der GUID über einen Neustart:** erst mit einem zweiten Lauf (gleicher Spielstand, gleiche Figuren) bestätigt. Fällt sie anders aus, gilt Ansatz A (Stimme nach Zeilen-ID, nur mit Geschlecht).
