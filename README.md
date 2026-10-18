# DrovaVoice (DrovaTTAI)

Deutsche KI-Stimmen für **Drova – Forsaken Kin**. Die Figuren sprechen ihre Dialoge, die Untertitel laufen wie gewohnt mit.

Das Projekt besteht aus zwei Teilen:

- **Generator** (`generator/`, Python, Befehl `drova-voice`): liest die Dialogtexte aus deiner eigenen Spielinstallation und erzeugt daraus Sprachdateien.
- **Mod** (`mod/`, C#, MelonLoader): spielt diese Dateien im Spiel ab.

Dieses Repo enthält **keine Spieltexte und kein Audio**. Beides entsteht lokal auf deinem Rechner aus deiner Spielkopie und liegt nicht im Git (`data/`, `cache/`, `out/` sind ausgeschlossen). Wer die Stimmen nutzen will, erzeugt sie selbst, mit der Anleitung unten.

Stand: Alle 245 benannten Sprecher haben eine Stimme, im Spiel sind rund 13.800 Zeilen vertont (41 Stimmen plus 7 Abwandlungen wie alte Frau, Riese, Zwerg). Dazu kommen Barks (Zurufe in der Welt, mit eigener Lautstärke und laufend leiser mit der Entfernung) und Zeilen generischer Figuren (`NPC`, Wache …): Dort wählt die Mod je Figur eine feste Stimme aus einem kleinen Pool nach Geschlecht. Nicht vertont sind die Antwortoptionen des Spielers (wie im Original), Briefe und Zeilen mit Quest- oder Geldwerten; Zeilen mit dem Spielernamen werden ohne den Namen gesprochen.

## Sprachsynthese: Fish Audio

Die Stimmen werden mit **[Fish Audio](https://fish.audio)** erzeugt (Modell `s2.1-pro-free`). Ich habe Fish gewählt, weil die Nutzung für Entwickler über die API kostenlos ist und die Qualität für Deutsch und für Emotionen im Text überzeugt hat. Das ist der Stand bei der Entwicklung (Oktober 2026); Fish kann Preise und Limits jederzeit ändern. Schau vor dem Vollauf in dein Konto, was aktuell gilt.

`s2.1-pro-free` ist laut Fish-Changelog dasselbe Modell wie `s2.1-pro` und kostenlos bis **30.11.2026**. Danach steht in der Preisliste `s2.1-pro` mit 15 USD je Million UTF-8-Bytes. Die Modell-ID steht an einer Stelle: `fish_model` in `generator/config.yaml`, sonst die Umgebungsvariable `FISH_MODEL`, sonst `s2.1-pro-free`. Der Cache-Schlüssel enthält das Modell (`fish-audio/<id>`), die Sprache aus `language`, die Latenz und die Sampling-Werte `temperature` und `top_p`. Ein Wechsel trifft keine vorhandene WAV. `synth` bricht dann ab und erzeugt erst nach `synth --accept-model-change` neu. Lässt du eine ID stehen, die Fish nicht mehr kennt, fällt die Anfrage laut TTS-Doku still auf `s2.1-pro` zurück und wird berechnet, ohne dass der Cache-Schlüssel sich ändert.

Wichtig zu wissen:

- Fish ist ein **Cloud-Dienst**. Der Sprechtext jeder Zeile wird an `api.fish.audio` gesendet. Es gelten die Bedingungen von Fish.
- Du brauchst ein eigenes Fish-Konto und einen **API-Schlüssel**. Der Schlüssel gehört nie in eine Datei oder ins Git. Der Generator liest ihn nur aus der Umgebungsvariable `FISH_API_KEY`.
- Die Stimmen in `casting/fish_voices.yaml` sind offizielle deutsche Fish-Stimmen und Stimmen aus der öffentlichen Fish-Bibliothek. **Bibliotheksstimmen von Community-Autoren sind nur für private, nicht-kommerzielle Nutzung gedacht.** Veröffentliche die erzeugten Audio-Dateien deshalb nicht und verkaufe sie nicht.
- Eine lokale Notlösung (Kitten TTS) ist als Rückfallebene vorbereitet, klingt aber deutlich schlechter. Begründung: `docs/decisions/2026-10-tts-engine.md`.

## Voraussetzungen

| Was | Wofür |
|---|---|
| Windows, Drova: Forsaken Kin (Steam) | Spiel und Mod (getestet mit Spielstand 2026-10, Unity 2022.3.45) |
| [MelonLoader](https://github.com/LavaGang/MelonLoader) 0.7.3 und die Drova Modding API 0.5.4 | Mod-Rahmen im Spiel |
| [.NET SDK](https://dotnet.microsoft.com/download) | Mod bauen |
| Python 3.11 oder neuer, am besten mit [uv](https://docs.astral.sh/uv/) | Generator |
| [ffmpeg](https://ffmpeg.org/) und ffprobe im `PATH`, ffmpeg mit `libvorbis` (für die Abwandlungen zusätzlich `rubberband`) | Audio kodieren |
| Fish-Konto mit API-Schlüssel | Stimmen erzeugen |
| Ca. 1 GB freier Platz | die fertigen Sprachdateien belegen rund 500 MB, dazu Zwischendateien |

Mache vor dem Installieren eine Kopie deines Spielordners. Wie man die Mod wieder restlos entfernt, steht in `docs/setup.md`.

## Anleitung

Alle Befehle sind für die Git Bash geschrieben. Ersetze den Spielpfad durch deinen eigenen.

### 1. Repo holen

```bash
git clone https://github.com/janphi001/DrovaTTAI.git
cd DrovaTTAI
```

### 2. MelonLoader und Modding API ins Spiel bringen

1. `MelonLoader.x64.zip` (v0.7.3) in den Spielordner entpacken, sodass `version.dll` und der Ordner `MelonLoader/` neben der Spiel-EXE liegen.
2. `Modding_API.zip` (release-0.5.4) ebenfalls in den Spielordner entpacken (es entstehen `Mods/` und `UserLibs/`).
3. Spiel einmal bis ins Hauptmenü starten und wieder beenden. Dabei erzeugt MelonLoader die Dateien unter `MelonLoader/Il2CppAssemblies`.

Mehr dazu und der Rückbau: `docs/setup.md`.

### 3. Mod bauen

Das Spiel muss dabei **geschlossen** sein. Der Build kopiert die Mod nur in den Spielordner, wenn `DeployToGame` gesetzt ist. Ohne die Eigenschaft wird nur kompiliert.

```bash
dotnet build mod/DrovaVoice/DrovaVoice.csproj -c Release -p:DeployToGame=true
```

Liegt das Spiel nicht unter dem Standardpfad, setze vorher die Umgebungsvariable `DROVA_GAME_DIR` auf den Spielordner.

### 4. Dialogtexte aus dem Spiel exportieren

Die Mod kann die Dialogbäume des Spiels in eine Datei schreiben. Dieser Export enthält Spieltexte und bleibt deshalb nur auf deinem Rechner.

1. Spiel starten und **im Hauptmenü** bleiben, das Spielfenster im Vordergrund. Keinen Spielstand laden.
2. Im Spielordner eine leere Datei `Mods/DrovaVoice/export.trigger` anlegen. Die Mod erkennt sie, löscht sie und schreibt die Ergebnisse nach `Mods/DrovaVoice/Export/de/`.
3. Warten, bis im Log (`MelonLoader/Latest.log`) die Meldung zum Export erscheint, dann **das Spiel beenden**. Ein Export im Hauptmenü macht die Vertonung in dieser Sitzung wirkungslos, deshalb nie direkt danach weiterspielen.
4. Zusätzlich `export-npcs.trigger` auf dieselbe Weise anlegen, das liefert die Sprecher- und Stimmenliste.

Einzelheiten und bekannte Eigenheiten: `docs/export.md`.

### 5. Generator einrichten

```bash
cd generator
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
cp config.example.yaml config.yaml
```

Trage in `generator/config.yaml` den Pfad zu deinem Spielordner ein (`game_dir`, mit `/` statt `\`) und die Sprache (`language: de`).

Dann den Export vom Spiel in den Arbeitsordner holen und prüfen:

```bash
.venv/Scripts/drova-voice export fetch
.venv/Scripts/drova-voice export report --manifest ../data/export/de/manifest-loaded.json
```

### 6. Fish-Schlüssel setzen

Den Schlüssel bekommst du in deinem Fish-Konto. Setze ihn nur für die aktuelle Shell:

```bash
export FISH_API_KEY="dein-schluessel"
```

Speichere ihn nirgends in einer Datei. Taucht er versehentlich irgendwo auf (Chat, Log, Git), setze ihn bei Fish sofort zurück.

### 7. Stimmen erzeugen

Der Generator arbeitet in Schritten und lässt sich jederzeit abbrechen und wieder aufnehmen (fertige Zeilen werden nicht noch einmal berechnet). Zum Ausprobieren eignet sich ein einzelner Sprecher:

```bash
cd generator
.venv/Scripts/drova-voice extract
.venv/Scripts/drova-voice cast --check --npc Adela
.venv/Scripts/drova-voice emote --npc Adela
.venv/Scripts/drova-voice synth --npc Adela      # schickt den Text an Fish
.venv/Scripts/drova-voice encode --npc Adela
.venv/Scripts/drova-voice install --npc Adela    # kopiert ins Spiel (--prune löscht verwaiste OGG)
.venv/Scripts/drova-voice report --npc Adela
```

Spiel starten, einen Spielstand laden, mit Adela sprechen: Du solltest ihre Stimme hören. Mit `synth --limit 20` erzeugst du zum Testen nur die ersten 20 Zeilen.

**Alle Figuren auf einmal** (Casting und Vollauf):

```bash
.venv/Scripts/drova-voice cast --propose         # Stimmen automatisch zuteilen
.venv/Scripts/drova-voice batches                # in Etappen nach Wichtigkeit aufteilen
.venv/Scripts/drova-voice synth --batch 1
.venv/Scripts/drova-voice encode --batch 1
.venv/Scripts/drova-voice install --batch 1
.venv/Scripts/drova-voice report --by-speaker    # Lücken je Sprecher
```

Das für alle Etappen zu wiederholen dauert Stunden und überträgt rund 850.000 Zeichen an Fish. Der Zeichenverbrauch steht am Ende jeder `synth`-Ausgabe. Bei Guthaben-, Limit- oder Anmeldefehlern bricht `synth` nach fünf Fehlern in Folge sauber ab. Danach kannst du später einfach weitermachen.

Alle Schritte und Optionen: `docs/generator.md`. Das Dateiformat der Sprachdateien: `docs/audio-format.md`.

### 8. Spielen und einstellen

Spiel starten, Spielstand laden, mit NPCs sprechen. Die Einstellungen stehen in `<Spiel>/UserData/MelonPreferences.cfg` im Abschnitt `[DrovaVoice]` (Änderungen gelten nach einem Neustart):

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `Enabled` | `true` | Vertonung an oder aus |
| `DialogVolume` | `100` | Lautstärke der NPC-Stimmen in Prozent (0 bis 200) |
| `PlayerVolume` | `100` | Lautstärke der Spielerzeilen in Prozent (0 bis 200) |
| `CacheMB` | `64` | Speicher für geladene Sprachclips |
| `Diagnostics` | `false` | ausführliches Log, hilft bei der Fehlersuche |

Weitere Hinweise, Log-Meldungen und die Abnahme-Checkliste: `docs/playback.md`.

## Verwendete Stimmen

Das Projekt nutzt **41 Fish-Stimmen** (22 männlich, 19 weiblich) und **7 Abwandlungen**. Alle stehen mit ihren Fish-IDs in `casting/fish_voices.yaml`; hier die Übersicht. Die Auswahl habe ich nach dem Anhören von Hörproben getroffen. Imitationen realer Personen habe ich vorab ausgeschlossen.

- **8 offizielle deutsche Fish-Stimmen** (Lena, Leon, Melanie, Lukas aus Österreich, Emma, Elin aus der Schweiz, Jonas, Valentina aus Österreich)
- **33 Stimmen aus der öffentlichen Fish-Bibliothek** (Community-Autoren; **nur private, nicht-kommerzielle Nutzung**)

| Schlüssel | Name bei Fish | Geschlecht | Herkunft | Alter | Quelle | Fish-ID |
|---|---|---|---|---|---|---|
| `lena` | Lena | weiblich | Deutschland |  | offiziell (Fish) | `3937b44b604249f18b94913daef94043` |
| `leon` | Leon | männlich | Deutschland |  | offiziell (Fish) | `7b7c88bf825a4ab3bca27d55c26ddf16` |
| `melanie` | Melanie | weiblich | Deutschland |  | offiziell (Fish) | `d979e92f9c8a489fa581f55f6b9e48da` |
| `lukas` | Lukas (Österreich) | männlich | Österreich |  | offiziell (Fish) | `c1e7cc926aa5469aa966c353094d4b0b` |
| `emma` | Emma | weiblich | Deutschland |  | offiziell (Fish) | `3235abc9a84b407d92f73539a5651720` |
| `elin` | Elin (Schweiz) | weiblich | Schweiz |  | offiziell (Fish) | `0b96bf70a20d47f6b9e825d9cfe0e8c8` |
| `jonas` | Jonas | männlich | Deutschland |  | offiziell (Fish) | `44f1ec96a51e429f8b87776cbc55a997` |
| `valentina` | Valentina (Österreich) | weiblich | Österreich |  | offiziell (Fish) | `e5fb46af69e0481fa0d2d0f209b07ae2` |
| `ben_9e3f0e` | Ben | männlich | Deutschland | jung | Bibliothek (Community) | `9e3f0ea9a0a44c4d9f0c422715d0229f` |
| `ben_9e0a50` | Ben | männlich | Deutschland | jung | Bibliothek (Community) | `9e0a50728a424b048575d286a79c42be` |
| `schales_7ef3ea` | Schales | männlich | Deutschland | jung | Bibliothek (Community) | `7ef3eae2ff754f398e90dbcafdb7c5c8` |
| `vorlesen_stimlagen_90042f` | Vorlesen Stimlagen | männlich | Deutschland | mittel | Bibliothek (Community) | `90042f762dbf49baa2e7776d011eee6b` |
| `german_d83fad` | German | männlich | Deutschland | mittel | Bibliothek (Community) | `d83fade735f4447698a08986de772c82` |
| `ben_a20517` | Ben | männlich | Deutschland | mittel | Bibliothek (Community) | `a20517d0d23048319e4ced960899187e` |
| `bao_de2_chau_e89195` | Bao DE2 Chau | männlich | Deutschland | mittel | Bibliothek (Community) | `e891954162584409bce5cf43aebd1726` |
| `german_wisdom_m_3130ae` | GERMAN WISDOM. M | männlich | Deutschland | mittel | Bibliothek (Community) | `3130ae7c3d844e2998978289c7c11c98` |
| `germany_d5f684` | GERMANY | männlich | Deutschland | mittel | Bibliothek (Community) | `d5f6842c9bc849408c4b6c2a51a1c044` |
| `deutscheman_voice_fur_ti_9c0305` | Deutscheman_voice_fur_tiktok | männlich | Deutschland | mittel | Bibliothek (Community) | `9c03054b93ee4eda8c1db08767fd8d45` |
| `adam_570cf0` | Adam | männlich | Deutschland | mittel | Bibliothek (Community) | `570cf019f1044c3cb2917553fdfa9d34` |
| `almanca_i_yi_ses_7d4cbb` | ALMANCA İYİ SES | männlich | Deutschland | mittel | Bibliothek (Community) | `7d4cbb1b490744e4a5b4bad4759ff751` |
| `german_father_c07993` | German Father | männlich | Deutschland | alt | Bibliothek (Community) | `c079932b47564fcfad0a9f6874a49df7` |
| `father_german_usama_14ccc0` | father German Usama | männlich | Deutschland | alt | Bibliothek (Community) | `14ccc066ad16414487b60195328eed29` |
| `p0_2765f2` | P0 | männlich | Deutschland | alt | Bibliothek (Community) | `2765f263701044409059e23206bdd47f` |
| `erz_hler_c23420` | Erzähler | männlich | Deutschland | alt | Bibliothek (Community) | `c2342039ff8248d4a335e5cc2091d40d` |
| `niko_ba082d` | niko | männlich | Deutschland | alt | Bibliothek (Community) | `ba082dea53e841aeb420dc612cb804ed` |
| `deep_783f5c` | DEEP | männlich | Deutschland | alt | Bibliothek (Community) | `783f5c7cb4f64ef48a7c7f5166bbdc01` |
| `emilia_german_194b99` | EMILIA GERMAN | weiblich | Deutschland | jung | Bibliothek (Community) | `194b99d7c27e462ea40694cddf1f7c96` |
| `natasha_deutsch_88b185` | Natasha Deutsch | weiblich | Deutschland | jung | Bibliothek (Community) | `88b185f908c04ebea8b6ff642c8fea82` |
| `tea_capcut_044275` | Tea (capcut) | weiblich | Deutschland | jung | Bibliothek (Community) | `04427518d0a043ae825b5185515882b5` |
| `frau_110e73` | Frau | weiblich | Deutschland | jung | Bibliothek (Community) | `110e739143fc4607a1754ba1b24d55cb` |
| `douchland_old_story_2ef205` | Douchland OLD STORY | weiblich | Deutschland | jung | Bibliothek (Community) | `2ef205fde3f9475eaf908f87736cafec` |
| `catrinja_c5b66a` | Catrinja | weiblich | Deutschland | mittel | Bibliothek (Community) | `c5b66a80d90749fc914c714e793d1a2f` |
| `deutsche_ansagestimme_a586d5` | Deutsche Ansagestimme | weiblich | Deutschland | mittel | Bibliothek (Community) | `a586d5007b0249f0b25f32a036b1713c` |
| `said_deb281` | said | weiblich | Deutschland | mittel | Bibliothek (Community) | `deb28100c45547c8871753ab1fdf9856` |
| `amira_german_b59d11` | Amira - German | weiblich | Deutschland | mittel | Bibliothek (Community) | `b59d1164746a48bf971f4a0fd2cbf814` |
| `almanca_yeni_22d4f9` | almanca yeni | weiblich | Deutschland | mittel | Bibliothek (Community) | `22d4f9243101493a82ad8d27694a2038` |
| `pia_87bebc` | Pia | weiblich | Deutschland | alt | Bibliothek (Community) | `87bebc5ad62a4deaaf254befad582453` |
| `lebhafte_junge_frau_37bab8` | Lebhafte junge Frau | weiblich | Deutschland | jung | Bibliothek (Community) | `37bab8e91a5a44fa853b41bc6a8730e8` |
| `m_dchen_6761f7` | mädchen | weiblich | Deutschland | jung | Bibliothek (Community) | `6761f7ebcbce46db89864f9ce0a2d242` |
| `kind_von_oben_578878` | Kind von oben | weiblich | Deutschland | kind | Bibliothek (Community) | `57887823e98a48e0a7c01819628ba59b` |
| `warmer_junger_mann_179999` | Warmer junger Mann | männlich | Deutschland | jung | Bibliothek (Community) | `1799997c77204a1b8753511fdf47f485` |

Leere Altersfelder bedeuten: bei den offiziellen Stimmen nicht angegeben. Die Fish-ID ist die Kennung der Stimme bei Fish (auch in der API). Die Bibliothek hat keine feste Lebensdauer: der Autor kann die Stimme löschen oder verstecken, Fish kann sie abnehmen, und `GET /model/{id}` liefert dann 404. Das Feld `pvc_release_state` kann `retiring` sein, mit Datum `pvc_retire_effective_at`. Vor einem Vollauf prüft `drova-voice cast --check-voices` die IDs, die die Besetzung wirklich nutzt. Ohne `FISH_API_KEY` überspringt der Befehl die Prüfung und macht keinen Aufruf. Einen Ersatz trägst du optional unter `fallbacks:` in `casting/fish_voices.yaml` ein (`stimme: andere_stimme`). Die Prüfung nennt ihn, `synth` wechselt nicht von selbst.

### Abwandlungen

Für Figuren, für die es keine passende Stimme gibt, formt `encode` eine Basisstimme per ffmpeg (`rubberband`) um: Tonhöhe, Klangfarbe und Tempo.

| Schlüssel | Basisstimme | Einsatz |
|---|---|---|
| `alte_frau` | `pia_87bebc` | alte Frauen |
| `alte_frau_rau` | `amira_german_b59d11` | alte Frauen, rauer |
| `riese` | `deep_783f5c` | Riesen (tief, langsam) |
| `zwerg` | `erz_hler_c23420` | Zwerge (hellere Klangfarbe) |
| `schurke_hell` | `german_d83fad` | helle Schurken |
| `jugendlicher` | `ben_9e3f0e` | Jugendliche |
| `knabe` | `schales_7ef3ea` | Jungen |

### Wer spricht mit welcher Stimme

- **Automatisch:** `drova-voice cast --propose` teilt allen 245 benannten Sprechern anhand von Steckbriefen (Geschlecht, Alter, Typ, in `casting/profiles.jsonl`) eine Stimme zu und schreibt das Ergebnis nach `casting/casting_auto.yaml`. Jede Stimme wird dabei auf mehrere Figuren verteilt (am häufigsten 7 bis 8 Figuren pro Stimme).
- **Von Hand** (`casting/casting.yaml`, gewinnt): Adela `melanie`, Jero `german_wisdom_m_3130ae`, Enya `lena`, Femke `schales_7ef3ea`, Gerion `lukas`, Gilwar `jonas`, Jola `emma`, Meluna `valentina`, Reija `lebhafte_junge_frau_37bab8`.
- **Spieler:** feste Stimme `leon` für alle Spielerzeilen.
- **Fehlt noch:** echte Kinderstimmen (nur `kind_von_oben_578878` und die Variante `knabe`), mehr alte Frauenstimmen und helle Männerstimmen.

## Stimmen anpassen

- **Besetzung:** `casting/casting.yaml` (von Hand) hat Vorrang vor der automatischen Zuteilung `casting/casting_auto.yaml`. Eintrag: `Name: {voice: schluessel}`. Die verfügbaren Schlüssel stehen in `casting/fish_voices.yaml`, dort auch die Abwandlungen (alte Frau, Riese, Zwerg und weitere).
- **Eine Zeile oder Figur neu erzeugen:** die passende WAV in `cache/synth/` löschen, dann `synth`, `encode` und `install` für den Sprecher wiederholen.
- **Eigene Stimme:** Fish kann Stimmen aus einer kurzen Aufnahme klonen. Hinweise zur Aufnahme: `docs/stimmaufnahme.md`.

## Fehlersuche

| Problem | Lösung |
|---|---|
| Keine Stimmen im Spiel | Log `MelonLoader/Latest.log` ansehen: Steht dort `Audio-Connector der Modding API ersetzt.` (erst nach dem Laden eines Spielstands)? Gibt es `Mods/DrovaVoice/Audio/de/index.json`? |
| Export bringt nichts | Im Hauptmenü und mit dem Fenster im Vordergrund auslösen, danach Spiel beenden (`docs/export.md`) |
| `synth` bricht ab | Fish-Guthaben, Limit oder Schlüssel prüfen und danach den Befehl wiederholen |
| Build schlägt fehl | Spiel schließen, Pfad (`DROVA_GAME_DIR`) prüfen |
| Alte Stimmen sprechen beim Herumlaufen | war ein Fehler, ist in der aktuellen Mod behoben (`docs/HANDOFF-bug-stale-audio.md`) |

## Weitere Dokumentation

- Entwurf: `docs/superpowers/specs/2026-10-10-drova-voice-design.md`
- Stand und Entscheidungen: `docs/HANDOFF.md`, `docs/decisions/`
- Spiel und Mod einrichten: `docs/setup.md`, Export: `docs/export.md`
- Generator: `docs/generator.md`, Wiedergabe: `docs/playback.md`, Dateiformat: `docs/audio-format.md`

## Rechtliches

Der Code steht unter der [MIT-Lizenz](LICENSE). Das gilt nur für den Code dieses Repos. *Drova – Forsaken Kin* und seine Texte gehören den Entwicklern und dem Publisher; das Projekt ist ein inoffizieller Fan-Mod und nicht mit ihnen verbunden. Die Stimmen kommen von Fish Audio und unterliegen deren Bedingungen und den Lizenzen der jeweiligen Stimmen (siehe oben).
