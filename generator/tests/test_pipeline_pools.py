import json
import shutil

import pytest

from drova_voice.cli import main
from drova_voice.lines import read_lines

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe nicht installiert",
)
BARK_BASE = "DT_World_Test|Dialog/World|Plh_1"


def _add_generic_bark(repo):
    loc = repo.game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    (loc / "World_de.loc").write_text("Plh_1 { Hey, du da! }\n", encoding="utf-8")
    manifest_path = repo.data / "export" / "de" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lines"].append(
        {
            "id": BARK_BASE,
            "tree": "DT_World_Test",
            "nodeId": 1,
            "nodeType": "statement",
            "actorName": "NPC",
            "category": "bark",
            "generic": True,
            "locaPath": "Dialog/World",
            "locaKey": "Plh_1",
            "text": "x",
            "gvars": [],
        }
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (repo.casting / "pools.yaml").write_text("pools:\n  m: [leon]\n  w: [lena]\n", encoding="utf-8")


def test_extract_keeps_the_generic_line_and_report_counts_one_line_per_pool_voice(
    pipeline_repo, capsys
):
    _add_generic_bark(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    assert main(base + ["extract"]) == 0
    assert any(
        l.id == BARK_BASE and l.generic for l in read_lines(pipeline_repo.data / "lines.jsonl")
    )
    capsys.readouterr()
    assert main(base + ["report", "--category", "bark"]) == 0
    out = capsys.readouterr().out
    assert (
        "bark: 2 Zeilen" in out
    )  # eine generische Zeile -> zwei Poolzeilen (vm1, vw1), ohne Fish noch offen
    assert "dialog" not in out


def test_category_filter_selects_only_that_category(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    assert main(base + ["extract"]) == 0
    capsys.readouterr()
    assert main(base + ["report", "--category", "player"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("player:") and "dialog" not in out
    assert main(base + ["report", "--category", "bark"]) == 0
    assert "keine Zeilen" in capsys.readouterr().out


@needs_ffmpeg
def test_pool_lines_are_installed_under_bark_with_a_variants_block(pipeline_repo, guarded):
    _add_generic_bark(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (
        ["extract"],
        ["synth", "--engine", "fake", "--workers", "2", "--category", "bark"],
        ["encode", "--category", "bark"],
        ["install", "--category", "bark"],
    ):
        assert guarded(lambda s=step: main(base + s)) == 0, step
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert set(index["entries"]) == {BARK_BASE + "#vm1", BARK_BASE + "#vw1"}
    assert all(e["file"].startswith("bark/") for e in index["entries"].values())
    assert index["variants"] == {BARK_BASE: ["vm1", "vw1"]}


@needs_ffmpeg
def test_second_install_keeps_pool_entries_and_dropping_the_pool_removes_them(
    pipeline_repo, guarded
):
    _add_generic_bark(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (
        ["extract"],
        ["synth", "--engine", "fake", "--workers", "2"],
        ["encode"],
        ["install"],
        ["install"],
    ):
        assert guarded(lambda s=step: main(base + s)) == 0, step
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert {BARK_BASE + "#vm1", BARK_BASE + "#vw1"} <= set(index["entries"])
    (pipeline_repo.casting / "pools.yaml").unlink()
    main(base + ["install"])
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert not any(BARK_BASE in i for i in index["entries"])


@needs_ffmpeg
def test_shrinking_the_pool_removes_the_dropped_voice_from_the_index(pipeline_repo, guarded):
    _add_generic_bark(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (
        ["extract"],
        ["synth", "--engine", "fake", "--workers", "2"],
        ["encode"],
        ["install"],
    ):
        assert guarded(lambda s=step: main(base + s)) == 0, step
    (pipeline_repo.casting / "pools.yaml").write_text("pools:\n  m: [leon]\n", encoding="utf-8")
    assert main(base + ["install"]) == 0
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert BARK_BASE + "#vm1" in index["entries"] and BARK_BASE + "#vw1" not in index["entries"]
    assert index["variants"] == {BARK_BASE: ["vm1"]}
