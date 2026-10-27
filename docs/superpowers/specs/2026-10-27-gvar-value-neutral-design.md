# Quest- und Geldwerte neutral sprechen (Design)

Stand 2026-10-27. Baut auf den Namensvarianten auf (`2026-10-15-namensvarianten-design.md`). Vertrag: `docs/audio-format.md`.

## Ziel
Zeilen mit Quest- oder Geldwerten (`$GVAR:QuestVars_…_Config.Preis$` usw.) waren als `gvar_value` stumm. Wo es sauber geht, sollen sie mit einer festen, ungenauen Menge gesprochen werden („ein paar Münzen“ statt „fünfzig Münzen“). Keine Sprachausgabe zur Laufzeit, keine Werte aus dem Spiel. Der Untertitel zeigt weiter den echten Text.

## Entscheidung
- Gleiches Muster wie beim Spielernamen: Die gesprochene Fassung ist die Variante `<Basis-ID>#neutral`. `Line.raw` bleibt der Originaltext.
- Lieber stumm als falsch: Ersetzt wird nur nach einer festen Liste. Alles andere bleibt `gvar_value`. Keine feineren Gründe; die Aufschlüsselung liefert `report --gvar-values`.

## Generator (`gvar_value.py`)
1. Variable einordnen (letzter Teil nach dem Punkt): enthält `name` → `name` (stumm); enthält ein Mengenwort (`preis`, `price`, `cost`, `kosten`, `gold`, `anzahl`, `count`, `runden`, `teilnehmer` …) → Menge; sonst `unknown` (stumm).
2. Bei einer Menge das Nomen direkt dahinter in `TEMPLATES` nachschlagen: Geldnomen → `currency`, gezählte Nomen → `count`. Fehlt es (kein Nomen, Einzahl, Ordnungszahl, Bindestrich-Wort) → `bare` (stumm).
3. Steht direkt davor ein Artikel, Possessiv-, Demonstrativ- oder Mengenwort oder eine Zahl („die“, „deine“, „etwa“): bei `currency` werden diese Wörter (auch mehrere hintereinander) samt Leerraum gestrichen, die Menge rückt an ihre Stelle („Gib mir deine … Münzen“ → „Gib mir ein paar Münzen“); die Großschreibung am Satzanfang richtet sich nach dem Text vor dem gestrichenen Wort. Ein alleinstehendes „ihr“ wird nicht gestrichen (kann Pronomen sein, „Gebt ihr … Gold“) → stumm. Bei `count` → stumm.
4. Ersetzen durch „ein paar“ (Mehrzahl) oder „etwas“ (Stoff: `Gold`, `Silber`); am Satzanfang groß. „ein paar“ wird nicht gebeugt, das Nomen bleibt wie geschrieben (Dativ steht als eigene Form in der Liste).
5. Bleibt ein Wert der Zeile stumm, bleibt die ganze Zeile stumm. Hat die Zeile auch den Spielernamen, muss danach `make_name_variants` eine neutrale Fassung liefern, sonst stumm.

Auswahloptionen bleiben vorher als `player_choice` stumm. Zeilen nur mit dem Spielernamen laufen wie bisher.

## Mod
Keine Änderung. `VoiceService.GetClip` und `HasEntry` nehmen über `AudioIndex.ResolveVariant(id, LineIds.NeutralVariant)` jede vorhandene `#neutral`-Variante.

## Fish und Cache
Der Cache-Schlüssel (`synth.make_key`) hängt an Engine, Modell, Stimme, Text und Parametern. Bestehende Zeilen behalten ihren Text, also auch ihren Schlüssel. Neu sind nur die `#neutral`-Zeilen der bisher stummen Wertzeilen; nur sie gehen an Fish. `synth` läuft nur nach ausdrücklichem Ja des Nutzers.

## Bestand
Auf diesem Rechner gibt es keine Spieldaten. Die Zählung macht `drova-voice report --gvar-values` nach `extract` auf dem Rechner mit Spieldaten.

## Risiken
- Die Mengenwörter im Variablennamen sind geraten (aus Beispielen wie `PackagePrice`, `Costs`). Echte Namen können anders heißen; dann bleiben die Zeilen stumm, und der Bericht zeigt sie.
- „ein paar“ kann die echte Menge stark untertreiben (500 Münzen). Das ist gewollt; der Untertitel nennt die Zahl.
- Generische Sprecher bekommen für `#neutral`-Zeilen keine Poolstimmen (wie bei den Namenszeilen, `pools.py`).
