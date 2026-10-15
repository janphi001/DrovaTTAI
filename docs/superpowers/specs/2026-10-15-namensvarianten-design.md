# Namensvarianten: Zeilen mit Spielernamen (Design)

Stand 2026-10-15. Baut auf Plan 4 (Wiedergabe) und Plan 5 (Casting, Vollauf) auf. Vertrag: `docs/audio-format.md`.

## Ziel
NPC-Zeilen, in denen der Spielername (`$GVAR:EVars_Player.Name$`) vorkommt, sollen im Spiel gesprochen werden. Bisher sind sie als `gvar` übersprungen und stumm.

## Entscheidung des Nutzers
Die Mod spielt bei diesen Zeilen **immer die neutrale Fassung** (Name weggelassen, z. B. „Hallo NAME!“ → „Hallo!“). Es gibt keine Laufzeitprüfung des Namens und keine `#arden`-Audios. Das Untertitelbild bleibt wie im Original (mit dem Namen des Spielers); nur die Stimme sagt ihn nicht.

## Umfang (Stand `data/lines.jsonl`, 395 Zeilen mit `gvar`)
| Gruppe | Zeilen | Behandlung |
|---|---|---|
| nur Spielername, neutrale Fassung gefunden (`make_name_variants(...).neutral`) | 95 | werden vertont als `<Basis-ID>#neutral` |
| nur Spielername, keine neutrale Fassung (Name mitten im Satz) | 150 | bleiben stumm, Status `gvar_name` im Bericht |
| Quest- oder Geldwerte (`PackagePrice`, `Costs`, Arena-Teilnehmer …) | 150 | bleiben stumm, Status `gvar_value` im Bericht |

Nicht im Umfang: handgeschriebene neutrale Fassungen für die 150 `gvar_name`-Zeilen, `#arden`-Audios, Werte-Vorlesen für Quest-Variablen, Spielerstimm-Sets.

## Generator
- `build_lines` (`lines.py`): Zeilen, deren einziger Platzhalter `EVars_Player.Name` ist, bekommen die neutrale Fassung als Sprechtext, wenn `make_name_variants` eine liefert. Die Zeilen-ID wird `with_variant(id, "neutral")`. `Line.raw` bleibt der Originaltext.
- Fehlt die neutrale Fassung, ist `skip = "gvar_name"`. Alle anderen Platzhalter ergeben `skip = "gvar_value"` (statt bisher `gvar`).
- `synth`, `encode` und `install` behandeln die Zeile wie jede andere. `install.py` kennt Varianten schon (`split_variant`, Block `variants`); im Plan zu prüfen: Bereinigung veralteter Einträge (`drop_ids`) und Zuordnung der Stimme über den Sprecher der Basis-Zeile.
- Bericht: neue Statuszeilen `gvar_name` und `gvar_value`, damit die offenen Gruppen sichtbar sind.
- Fish-Verbrauch: 95 Zeilen. `synth` läuft nur nach ausdrücklichem Ja des Nutzers, der Key kommt vom Nutzer im Einzelbefehl.

## Mod
- `VoiceService.GetClip(id)` schlägt zuerst `<id>#neutral` nach, sonst `<id>`. `LineIds` hat den Trenner (`VariantSeparator`) schon.
- Der Nachschlag gilt für Dialog-Aussagen. Auswahloptionen bleiben stumm (unverändert).
- `AudioIndex` muss `variants` nicht lesen.
- Cache und Fehlerliste führen die Variante als eigene ID, nichts weiter.

## Tests
- Python (erfundene Texte): Platzhalter mit neutraler Fassung → ID mit `#neutral`, sprechbar; ohne neutrale Fassung → `gvar_name`; Quest-Wert → `gvar_value`; gemischte Platzhalter → `gvar_value`; `install` schreibt `#neutral`-Einträge samt `variants`.
- C# (xUnit, Core): Variante gewinnt, ohne Variante gilt die Basis-ID. Die Auswahl liegt dazu in einer Core-Funktion, damit sie ohne Spiel testbar ist.
- Hörtest im Spiel nimmt der Nutzer ab.

## Dokumentation
`docs/audio-format.md` (Aussage zu `$GVAR`-Zeilen), `docs/playback.md` (Hinweis „Namensvarianten fehlen“ entfällt), `docs/generator.md` (Zeile zu übersprungenen `gvar`) und `docs/HANDOFF.md` werden angepasst.

## Risiken
- Die neutrale Fassung kann den Satz verkürzen oder holprig machen. Die Regeln in `player_name.py` sind bereits getestet; der Nutzer hört die 95 Zeilen im Spiel an.
- Neue Zeilen-IDs verschieben nichts an bestehenden Einträgen; der Index wächst um höchstens 95 Einträge.
