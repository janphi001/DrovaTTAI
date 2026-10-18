import json
from pathlib import Path

import pytest

from drova_voice.cli import main
from drova_voice.export_report import compute_coverage, format_report, in_scope, loca_path_of


def _loc(root: Path, rel: str, keys: list[str]):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(f"{k} {{ Erfundener Text {i}. }}" for i, k in enumerate(keys)) + "\n", encoding="utf-8")


def _line(path: str, key: str):
    return {"id": f"DT_Test|{path}|{key}", "locaPath": path, "locaKey": key, "category": "dialog"}


@pytest.fixture
def loc_dir(tmp_path):
    d = tmp_path / "Localization" / "de"
    _loc(d, "Dialog/NPC_A_de.loc", ["Plh_1", "Plh_2", "Plh_3", "Plh_4"])
    _loc(d, "Dialogues/Quest_B_de.loc", ["Plh_1"])
    _loc(d, "IntroWorldDialog_de.loc", ["W_1"])
    _loc(d, "Letters/Brief_de.loc", ["L_1"])       # außerhalb des Umfangs
    _loc(d, "Items_de.loc", ["Sword_name"])        # außerhalb des Umfangs
    return d


def test_scope_covers_dialog_folders_and_world_files_only():
    assert in_scope(Path("Dialog/NPC_A_de.loc")) and in_scope(Path("Dialogues/Q_de.loc")) and in_scope(Path("Dialogue/Q_de.loc"))
    assert in_scope(Path("IntroWorldDialog_de.loc")) and in_scope(Path("Sub/Foo_World_de.loc"))
    assert not in_scope(Path("Letters/Brief_de.loc")) and not in_scope(Path("Items_de.loc"))


def test_loca_path_drops_extension_and_language_suffix(loc_dir):
    assert loca_path_of(loc_dir / "Dialog" / "NPC_A_de.loc", loc_dir, "de") == "Dialog/NPC_A"
    assert loca_path_of(loc_dir / "IntroWorldDialog_de.loc", loc_dir, "de") == "IntroWorldDialog"


def test_coverage_counts_covered_missing_and_extra(loc_dir):
    manifest = {"lines": [_line("Dialog/NPC_A", "Plh_1"), _line("Dialog/NPC_A", "Plh_2"), _line("Dialog/NPC_A", "Plh_3"),
                          _line("Dialogues/Quest_B", "Plh_1"), _line("Dialog/NPC_A", "Plh_99")]}
    cov = compute_coverage(manifest, loc_dir, "de")
    assert (cov.total, cov.covered, cov.extra) == (6, 4, 1)
    assert cov.percent == pytest.approx(100 * 4 / 6)
    assert cov.missing == ("Dialog/NPC_A:Plh_4", "IntroWorldDialog:W_1")
    assert cov.by_folder["Dialog"] == (4, 3)


def test_paths_are_compared_normalised(loc_dir):
    manifest = {"lines": [_line("Dialog\\NPC_A/", "Plh_1")]}
    assert compute_coverage(manifest, loc_dir, "de").covered == 1


def test_empty_scope_is_fully_covered(tmp_path):
    (tmp_path / "de").mkdir()
    assert compute_coverage({"lines": []}, tmp_path / "de", "de").percent == 100.0


def test_report_text_names_the_numbers_and_the_missing_file(loc_dir, tmp_path):
    cov = compute_coverage({"lines": [_line("Dialog/NPC_A", "Plh_1")]}, loc_dir, "de")
    text = format_report(cov, tmp_path / "coverage_missing.txt")
    assert "Abdeckung" in text and "1 von 6" in text and "coverage_missing.txt" in text


def _repo(tmp_path, loc_dir_game):
    gen = tmp_path / "repo" / "generator"
    gen.mkdir(parents=True)
    cfg = gen / "config.yaml"
    cfg.write_text(f'game_dir: "{loc_dir_game.as_posix()}"\n', encoding="utf-8")
    return tmp_path / "repo", cfg


def _game_with_loc(tmp_path, loc_dir):
    game = tmp_path / "game"
    target = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de"
    target.parent.mkdir(parents=True)
    loc_dir.rename(target)
    return game


def test_cli_report_returns_1_below_threshold_and_writes_the_missing_list(tmp_path, loc_dir, capsys):
    repo, cfg = _repo(tmp_path, _game_with_loc(tmp_path, loc_dir))
    manifest = repo / "data" / "export" / "de" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"lines": [_line("Dialog/NPC_A", "Plh_1")]}), encoding="utf-8")
    assert main(["--config", str(cfg), "export", "report"]) == 1
    assert (manifest.parent / "coverage_missing.txt").read_text(encoding="utf-8").count("\n") == 5
    assert main(["--config", str(cfg), "export", "report", "--min-coverage", "10"]) == 0
    assert "Abdeckung" in capsys.readouterr().out


def test_cli_report_without_manifest_exits_2(tmp_path, loc_dir, capsys):
    repo, cfg = _repo(tmp_path, _game_with_loc(tmp_path, loc_dir))
    assert main(["--config", str(cfg), "export", "report"]) == 2
    assert "Manifest nicht gefunden" in capsys.readouterr().err


def test_cli_fetch_copies_the_export_folder_from_the_game(tmp_path, loc_dir, capsys):
    game = _game_with_loc(tmp_path, loc_dir)
    repo, cfg = _repo(tmp_path, game)
    src = game / "Mods" / "DrovaVoice" / "Export" / "de"
    src.mkdir(parents=True)
    (src / "manifest.json").write_text('{"lines": []}', encoding="utf-8")
    assert main(["--config", str(cfg), "export", "fetch"]) == 0
    assert (repo / "data" / "export" / "de" / "manifest.json").read_text(encoding="utf-8") == '{"lines": []}'
    assert main(["--config", str(cfg), "export", "fetch"]) == 0  # wiederholbar


def test_unreadable_entry_counts_as_uncovered(tmp_path):
    d = tmp_path / "de"
    (d / "Dialog").mkdir(parents=True)
    (d / "Dialog" / "NPC_C_de.loc").write_text("Plh_1 { Erfundener Text. }\nPlh_2 kaputt ohne Klammer\n", encoding="utf-8")
    cov = compute_coverage({"lines": [_line("Dialog/NPC_C", "Plh_1")]}, d, "de")
    assert (cov.total, cov.covered, cov.unreadable) == (2, 1, 1)
    assert len(cov.missing) == 1 and "unlesbar" in cov.missing[0]
    assert cov.by_folder["Dialog"] == (2, 1)
    assert cov.percent == 50.0


def test_cli_report_fails_when_loc_folder_is_missing(tmp_path, capsys):
    game = tmp_path / "game"
    game.mkdir()
    repo, cfg = _repo(tmp_path, game)
    assert main(["--config", str(cfg), "export", "report"]) == 2
    assert "Lokalisierungsordner nicht gefunden" in capsys.readouterr().err


def test_cli_report_fails_when_no_entries_are_in_scope(tmp_path, capsys):
    d = tmp_path / "Localization" / "de"
    _loc(d, "Items_de.loc", ["Sword_name"])
    repo, cfg = _repo(tmp_path, _game_with_loc(tmp_path, d))
    manifest = repo / "data" / "export" / "de" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"lines": []}', encoding="utf-8")
    assert main(["--config", str(cfg), "export", "report"]) == 2
    assert "Keine .loc-Einträge im Umfang" in capsys.readouterr().err


def _text_line(path, key, text, gvars=None, **extra):
    return {**_line(path, key), "text": text, "gvars": gvars or [], **extra}


def test_text_cross_check_ignores_whitespace_and_lists_only_labels(tmp_path):
    d = tmp_path / "de"
    (d / "Dialog").mkdir(parents=True)
    body = "\n".join(f"K_{i} {{ Erfundener  Text {i}. }}" for i in range(8)) + "\n"
    (d / "Dialog" / "NPC_T_de.loc").write_text(body, encoding="utf-8")
    lines = [_text_line("Dialog/NPC_T", "K_0", "Erfundener Text 0.\n"),  # nur Leerraum anders: gleich
             *[_text_line("Dialog/NPC_T", f"K_{i}", "Ganz anderer Text.") for i in range(1, 7)]]  # 6 Abweichungen
    cov = compute_coverage({"lines": lines}, d, "de")
    assert (cov.text_checked, cov.text_mismatch) == (7, 6)
    assert len(cov.text_mismatch_examples) == 5 and cov.text_mismatch_examples[0] == "Dialog/NPC_T:K_1"
    assert cov.covered == 7 and cov.percent == pytest.approx(100 * 7 / 8)  # Prozent unberührt
    text = format_report(cov, tmp_path / "m.txt")
    assert "Text weicht von der .loc ab: 6 von 7" in text and "Dialog/NPC_T:K_1" in text
    assert "Ganz anderer" not in text and "Erfundener" not in text


def test_gvar_check_counts_loc_placeholders_without_manifest_gvars(tmp_path):
    d = tmp_path / "de"
    (d / "Dialog").mkdir(parents=True)
    (d / "Dialog" / "NPC_G_de.loc").write_text(
        "G_1 { Hallo $GVAR:EVars_Player.Name$. }\nG_2 { Wieder $GVAR:EVars_Player.Name$. }\nG_3 { Ohne. }\n", encoding="utf-8")
    lines = [_text_line("Dialog/NPC_G", "G_1", "Hallo $GVAR:EVars_Player.Name$.", gvars=["EVars_Player.Name"]),
             _text_line("Dialog/NPC_G", "G_2", "Wieder Fremder."),
             _text_line("Dialog/NPC_G", "G_3", "Ohne.")]
    cov = compute_coverage({"lines": lines}, d, "de")
    assert (cov.gvar_checked, cov.gvar_missing) == (2, 1)
    assert "leere gvars im Manifest: 1 von 2" in format_report(cov, tmp_path / "m.txt")


def test_cli_report_exit_code_ignores_text_mismatch(tmp_path, loc_dir):
    repo, cfg = _repo(tmp_path, _game_with_loc(tmp_path, loc_dir))
    manifest = repo / "data" / "export" / "de" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    lines = [_text_line(p, k, "Falscher Text.") for p, k in [("Dialog/NPC_A", f"Plh_{i}") for i in range(1, 5)]
             + [("Dialogues/Quest_B", "Plh_1"), ("IntroWorldDialog", "W_1")]]
    manifest.write_text(json.dumps({"lines": lines}), encoding="utf-8")
    assert main(["--config", str(cfg), "export", "report"]) == 0


def test_breakdown_counts_categories_and_top_combinations(tmp_path):
    d = tmp_path / "de"
    (d / "Dialog").mkdir(parents=True)
    (d / "Dialog" / "NPC_B_de.loc").write_text("B_1 { Erfunden. }\n", encoding="utf-8")
    lines = []
    for i in range(20):  # 20 verschiedene Sprecher, je eine Zeile
        lines.append({**_line("Dialog/NPC_B", f"X_{i}"), "actorName": f"Actor{i:02d}", "nodeType": "statement", "category": "dialog"})
    lines += [{**_line("Dialog/NPC_B", f"P_{i}"), "actorName": "Player", "nodeType": "choice", "category": "player"} for i in range(5)]
    lines.append({**_line("Dialog/NPC_B", "B_1"), "actorName": "x" * 100, "nodeType": "statement", "category": "dialog"})
    cov = compute_coverage({"lines": lines}, d, "de")
    assert cov.lines_total == 26 and cov.player_lines == 5
    assert cov.by_category == {"dialog": 21, "player": 5}
    assert len(cov.by_actor) == 15 and cov.by_actor[0] == (("Player", "choice", "player"), 5)
    text = format_report(cov, tmp_path / "m.txt")
    assert "davon player: 5 (19.2 %)" in text and "Je Kategorie: dialog 21, player 5" in text
    assert "x" * 100 not in text
    assert text.count("\n") < 40  # Länge begrenzt


def test_coverage_rejects_a_loc_file_that_is_not_utf8(tmp_path):
    d = tmp_path / "de"
    (d / "Dialog").mkdir(parents=True)
    (d / "Dialog" / "NPC_B_de.loc").write_bytes(b"B_1 { Aa\xe4 }\n")
    with pytest.raises(ValueError, match="kein gültiges UTF-8") as info:
        compute_coverage({"lines": []}, d, "de")
    assert "Aa" not in str(info.value) and "\ufffd" not in str(info.value)


def test_old_style_coverage_construction_still_works():
    from drova_voice.export_report import Coverage
    cov = Coverage(total=1, covered=1, missing=(), extra=0, by_folder={})
    assert "Text weicht von der .loc ab: 0 von 0" in format_report(cov, Path("m.txt"))
