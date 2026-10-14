from drova_voice.cli import main


def test_cast_check_ok(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check"]) == 0
    out = capsys.readouterr().out
    assert "lena: 2" in out and "leon: 1" in out and "ohne Stimme: keine" in out


def test_cast_check_reports_missing_speaker(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check"]) == 1
    assert "Mira: 2" in capsys.readouterr().out


def test_cast_check_unknown_voice_fails_before_running(pipeline_repo, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers:\n  mira: {voice: erfunden}\n", encoding="utf-8")
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "cast", "--check"]) == 2
    assert "erfunden" in capsys.readouterr().err
