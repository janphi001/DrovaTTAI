from drova_voice.cli import main
from ffmpeg_marks import needs_rubberband

FISH = (
    "voices:\n  lena: {id: '3937b44b604249f18b94913daef94043', label: Lena, gender: f}\n"
    "  leon: {id: '7b7c88bf825a4ab3bca27d55c26ddf16', label: Leon, gender: m}\n"
    "variants:\n  alte: {base: lena, label: Alte, gender: f, age: alt, pitch: 0.9, formant: 1.0, tempo: 0.9}\n"
)


@needs_rubberband
def test_encode_uses_the_variant_of_the_speaker(pipeline_repo, guarded):
    (pipeline_repo.casting / "fish_voices.yaml").write_text(FISH, encoding="utf-8")
    (pipeline_repo.casting / "casting.yaml").write_text(
        "default_player: leon\nspeakers:\n  mira: {voice: alte}\n", encoding="utf-8"
    )
    cfg = str(pipeline_repo.cfg)
    assert main(["--config", cfg, "extract"]) == 0
    assert (
        guarded(lambda: main(["--config", cfg, "synth", "--engine", "fake", "--workers", "2"])) == 0
    )
    assert main(["--config", cfg, "encode"]) == 0
    stamps = list((pipeline_repo.repo / "out" / "audio" / "de" / "dialog").glob("*.stamp"))
    assert len(stamps) == 2 and all("rubberband" in s.read_text(encoding="utf-8") for s in stamps)
    player_stamps = list((pipeline_repo.repo / "out" / "audio" / "de" / "player").rglob("*.stamp"))
    assert player_stamps and all(
        "rubberband" not in s.read_text(encoding="utf-8") for s in player_stamps
    )
