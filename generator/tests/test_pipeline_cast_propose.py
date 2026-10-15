from drova_voice.cli import main


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def prepare(repo):
    (repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    run(repo, "extract")


def test_propose_writes_the_auto_file_and_check_accepts_it(pipeline_repo, capsys):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    assert run(pipeline_repo, "cast", "--propose") == 0
    assert "mira" in (pipeline_repo.casting / "casting_auto.yaml").read_text(encoding="utf-8")
    capsys.readouterr()
    assert run(pipeline_repo, "cast", "--check") == 0
    assert "lena: 2" in capsys.readouterr().out


def test_propose_reports_speakers_without_profile(pipeline_repo, capsys):
    prepare(pipeline_repo)
    assert run(pipeline_repo, "cast", "--propose") == 1
    assert "mira" in capsys.readouterr().out.lower()


def test_manual_casting_wins_and_keep_retains_the_auto_entries(pipeline_repo):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    run(pipeline_repo, "cast", "--propose")
    auto = pipeline_repo.casting / "casting_auto.yaml"
    first = auto.read_text(encoding="utf-8")
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "m", "--age", "mittel")  # Steckbrief ändert sich
    assert run(pipeline_repo, "cast", "--propose", "--keep") == 0
    assert auto.read_text(encoding="utf-8") == first  # abgenommene Besetzung bleibt
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers:\n  mira: {voice: leon}\n", encoding="utf-8")
    assert run(pipeline_repo, "cast", "--propose") == 0
    assert "mira" not in auto.read_text(encoding="utf-8").split("speakers:")[1]  # von Hand besetzt: nicht mehr in Auto


def test_check_reports_overuse_and_scene_conflicts(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers:\n  mira: {voice: lena}\n", encoding="utf-8")
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "cast", "--check", "--max-speakers", "0") == 0
    assert "Überbelegt" in capsys.readouterr().out
