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
