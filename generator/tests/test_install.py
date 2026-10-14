import json

from drova_voice.install import install_audio, split_variant


def make_audio(audio_dir, rel, content=b"OggS-Test"):
    path = audio_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def row(id_, rel, duration=1.5):
    return {"id": id_, "rel": rel, "duration": duration, "key": "k"}


def read_index(install_dir):
    return json.loads((install_dir / "index.json").read_text(encoding="utf-8"))


def test_split_variant():
    assert split_variant("T|P|Plh_1") == ("T|P|Plh_1", None)
    assert split_variant("T|P|Plh_1#arden") == ("T|P|Plh_1", "arden")
    assert split_variant("T|P|Plh_1|c2#m1") == ("T|P|Plh_1|c2", "m1")


def test_install_copies_files_and_writes_index(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "game" / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "player/default/bbbb.ogg")
    result = install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg", 1.23456), row("T|P|Plh_2|c0", "player/default/bbbb.ogg")],
                           audio, target, "de")
    assert (result.copied, result.entries, result.errors) == (2, 2, [])
    assert (target / "dialog" / "aaaa.ogg").read_bytes() == b"OggS-Test"
    index = read_index(target)
    assert index["version"] == 1 and index["language"] == "de"
    assert index["entries"]["T|P|Plh_1"] == {"file": "dialog/aaaa.ogg", "duration": 1.235}
    assert index["entries"]["T|P|Plh_2|c0"]["file"] == "player/default/bbbb.ogg" and index["variants"] == {}


def test_second_install_keeps_earlier_entries(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/cccc.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    install_audio([row("U|Q|Plh_1", "dialog/cccc.ogg")], audio, target, "de")
    assert sorted(read_index(target)["entries"]) == ["T|P|Plh_1", "U|Q|Plh_1"]


def test_missing_source_is_an_error_and_not_indexed(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    result = install_audio([row("T|P|Plh_1", "dialog/weg.ogg")], audio, target, "de")
    assert result.entries == 0 and len(result.errors) == 1 and "Plh_1" in result.errors[0]
    assert read_index(target)["entries"] == {}


def test_entries_whose_file_vanished_are_dropped(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    (target / "dialog" / "aaaa.ogg").unlink()
    install_audio([], audio, target, "de")
    assert read_index(target)["entries"] == {}


def test_variants_and_umlauts(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/bbbb.ogg")
    install_audio([row("DT_Bär|P|Plh_1#neutral", "dialog/aaaa.ogg"), row("DT_Bär|P|Plh_1#arden", "dialog/bbbb.ogg")],
                  audio, target, "de")
    text = (target / "index.json").read_text(encoding="utf-8")
    assert "DT_Bär" in text and "\\u" not in text
    assert read_index(target)["variants"] == {"DT_Bär|P|Plh_1": ["arden", "neutral"]}


def test_unchanged_files_are_not_copied_again(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    assert install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de").copied == 0


def test_drop_ids_remove_entries_of_lines_that_are_no_longer_installed(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/bbbb.ogg")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg"), row("T|P|Plh_2#arden", "dialog/bbbb.ogg")], audio, target, "de")
    install_audio([], audio, target, "de", drop_ids={"T|P|Plh_2"})  # Varianten gehören zur Basis-ID
    index = read_index(target)
    assert sorted(index["entries"]) == ["T|P|Plh_1"] and index["variants"] == {}
