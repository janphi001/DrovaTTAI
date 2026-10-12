# Befunde aus dem ersten Export (M1), 2026-10-12

Gemessen im Hauptmenü mit `export.trigger` und `export-npcs.trigger`; Zahlen und Klassennamen, keine Spieltexte.

## R1: Abdeckung der Dialogbäume
- Im Speicher liegen 1.807 Dialogbäume (`Resources.FindObjectsOfTypeAll<DialogueTree>()`), davon 156 als Test/Debug markiert und übersprungen; 1.651 exportiert, 1.547 davon liefern Zeilen. Ergebnis: **19.535 Zeilen** (13.044 Aussagen, 6.491 Auswahloptionen), 408 doppelte IDs (gleiche Bäume mehrfach geladen) übersprungen, 5 ohne Text.
- **Abdeckung gegen die `.loc`-Dateien: 93,55 %** (17.143 von 18.324 Einträgen); ohne Test-/Vorlagendateien (114 Einträge) 94,1 %. Das 98-%-Ziel aus Spec §5 wird mit Bäumen allein **nicht** erreicht.
- Die Lücke (1.181 Einträge, 61 Dateien) liegt fast vollständig in Welt-Dialog-Dateien (`RestWorldDialogue` 352, `NewWorldDialog` 100, `Dialogues/WorldDialogue` 59, `NemetonWorldDialog` 52, `BrutusMineWorldDialog` 49, `RuinenlagerWorldDialog` 41, `WorldDialog_RedTower` 36, `LastWorldDialogues` 27 …) und in einzelnen NPC-Dateien (`NPC_Karotte` 48, `Teaching` 53, `NPC_Mombert` 29, `NPC_Reija` 22). Vermutung: Einträge ohne Baum im Speicher (unbenutzt oder in Szenen-Graphen, die erst mit der Szene entstehen). Ein Spielstand ändert die Baumzahl nicht (1.651 vorher wie nachher).
- Der Katalogweg (`export-all.trigger`) funktioniert nicht: die `m_InternalIds` sind keine Addressables-Schlüssel, `LoadAssetAsync<DialogueTree>` und `LoadAssetAsync<Object>` liefern für alle Adressen `null`. Er ist auch nicht nötig: der Speicher enthält praktisch alle `DT_*`-Assets (Katalog: 1.787 Adressen). Der Schreibschutz hat dabei verhindert, dass ein leeres `manifest.json` entstand.
- **Entscheidung für den Nutzer (Spec R1):** Notlösung für die fehlenden ~6,5 % aus den `.loc`-Dateien (Sprecher per LLM zuordnen), oder Szenen mit Welt-Dialogen im Spiel besuchen und erneut exportieren. Test-/Vorlagendateien können ausgeschlossen werden.

## Technische Befunde zum Export
- Die Modding API hängt an `Graph.SelfDeserialize` einen Postfix (`DialogueTreePatch`) an, dessen `AudioManager`-Initialisierung im Hauptmenü mit einer `TypeInitializationException` scheitert, nachdem die Deserialisierung fertig ist. Der Exporter fängt diese Ausnahme ab (1.651-mal gezählt). Frisch geladene Bäume sind nie vorab deserialisiert (0 von 1.651), der Aufruf ist also nötig.
- Nach dem Laden eines Spielstands und einem Export hing das Spiel; im Log standen Fehler aus `MainThreadDispatcher.Drain` (Postfix-Aufgaben der Modding API). **Empfehlung: Export nur im Hauptmenü, danach das Spiel beenden, keinen Spielstand laden.**
- Das Spiel pausiert `Update` im Hintergrund: Das Fenster muss vorn liegen, sonst wird `export.trigger` nicht erkannt.
- `GetLocalizedString()` liefert den Text **mit eingesetzten Variablen**; `$GVAR:`-Platzhalter fehlen im Manifest (`gvars` überall leer, 515 Zeilen betroffen). Für die Sprachausgabe bleibt der Text der `.loc` die Quelle für Zeilen mit Platzhaltern (Python gleicht Manifest und `.loc` pro Schlüssel ab). Woher die Variablenwerte zur Laufzeit kommen, wurde noch nicht untersucht (Namespace `Il2CppDrova.GlobalVarSystem`).
- Knotentypen: `GetType().Name` liefert für alle Knoten `Node` (Il2Cpp-Hülle); der Zähler ignorierter Knotentypen ist so nicht aussagekräftig (17.365 ignorierte Knoten).

## Kategorien und Sprecher
- 12.598 `dialog`, 6.610 `player` (**33,8 %**), 327 `bark`; 360 Zeilen mit generischem Sprecher (`NPC` 338, `Teacher` 10, `Druid` 5, `Actor` 4, `Participant` 3). 290 verschiedene Sprecher.
- Spielerzeilen: 6.491 Auswahloptionen + 119 Aussagen, alle mit Sprecher `Player`; `INSTIGATOR` kommt nicht vor. Die Klassifizierung stimmt, keine Änderung an `LineClassifier` nötig.

## R4: NPC-Daten
- `npcs.json`: 332 `EntityInfo` im Hauptmenü, 420 mit geladenem Spielstand, alle mit Anzeigename. `voices.json`: 13 `VoiceMap`-Assets (`voiceId`: `Default_Male`/`Default_Female`/`Player_Male`/`Player_Female` plus 9 benannte Sprecher; `bodyType`: `Strong`/`Petite`).
- `EntityInfo` und `VoiceMap` haben **kein Geschlecht** und keine NPC-Zuordnung. Kandidat: die Komponente `ActorBodyType` an den Akteuren (`_bodyType`, `_voiceId`, `_voiceMap`, `GetBodyType`, `GetVoiceId`, `SetGender`) sowie `VoiceUtil.TryGetGender`; erreichbar nur über Akteure in geladenen Szenen. Für Plan 3: Geschlecht aus `bodyType`/`voiceId` ableiten, wo vorhanden, sonst per LLM aus Steckbrief schätzen (Spec R4).
