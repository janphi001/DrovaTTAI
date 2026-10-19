from drova_voice.cli import main


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def prepare(repo):
    (repo.casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers: {}\n", encoding="utf-8"
    )
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


def test_second_propose_keeps_the_auto_entries_and_reset_reassigns(pipeline_repo, capsys):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    run(pipeline_repo, "cast", "--propose")
    assert (
        "Neu zugeteilt" in capsys.readouterr().out
    )  # erste Zuteilung: es gibt noch keine Auto-Datei
    auto = pipeline_repo.casting / "casting_auto.yaml"
    first = auto.read_text(encoding="utf-8")
    run(
        pipeline_repo, "profile", "--set", "mira", "--gender", "m", "--age", "mittel"
    )  # Steckbrief ändert sich
    assert run(pipeline_repo, "cast", "--propose") == 0  # ohne --keep: bisherige Zuteilung bleibt
    assert auto.read_text(encoding="utf-8") == first
    assert "Bisherige Auto-Zuteilung bleibt" in capsys.readouterr().out
    assert (
        run(pipeline_repo, "cast", "--propose", "--keep") == 0
    )  # --keep bleibt als Synonym erlaubt
    assert auto.read_text(encoding="utf-8") == first
    assert run(pipeline_repo, "cast", "--propose", "--reset") == 0
    assert (
        "leon" in auto.read_text(encoding="utf-8") and auto.read_text(encoding="utf-8") != first
    )  # neu zugeteilt
    assert "Neu zugeteilt (--reset)" in capsys.readouterr().out


def test_manual_casting_is_excluded_from_the_auto_file(pipeline_repo):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    run(pipeline_repo, "cast", "--propose")
    auto = pipeline_repo.casting / "casting_auto.yaml"
    assert "mira" in auto.read_text(encoding="utf-8")
    (pipeline_repo.casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers:\n  mira: {voice: leon}\n", encoding="utf-8"
    )
    assert run(pipeline_repo, "cast", "--propose") == 0
    assert (
        "mira" not in auto.read_text(encoding="utf-8").split("speakers:")[1]
    )  # von Hand besetzt: nicht mehr in Auto


def test_stale_voice_key_in_the_old_auto_file_blocks_keep_but_not_reset(pipeline_repo):
    prepare(pipeline_repo)
    run(pipeline_repo, "profile", "--set", "mira", "--gender", "f", "--age", "mittel")
    auto = pipeline_repo.casting / "casting_auto.yaml"
    auto.write_text('speakers:\n  "mira": {voice: geist}\n', encoding="utf-8")
    assert (
        run(pipeline_repo, "cast", "--propose") != 0
    )  # bleibt: veralteter Schlüssel wird gemeldet
    assert "geist" in auto.read_text(encoding="utf-8")
    assert (
        run(pipeline_repo, "cast", "--propose", "--reset") == 0
    )  # verwerfen: alte Datei wird gar nicht erst geprüft
    assert "lena" in auto.read_text(encoding="utf-8") and "geist" not in auto.read_text(
        encoding="utf-8"
    )


def test_check_reports_overuse_and_scene_conflicts(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers:\n  mira: {voice: lena}\n", encoding="utf-8"
    )
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "cast", "--check", "--max-speakers", "0") == 0
    assert "Überbelegt" in capsys.readouterr().out


def test_listen_writes_the_sheet(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "cast", "--listen") == 0
    page = pipeline_repo.repo / "out" / "casting" / "index.html"
    assert page.is_file() and "Mira" in page.read_text(encoding="utf-8")
