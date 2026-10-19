import json
import zipfile

import pytest

from drova_voice.release import build_package, indexed_audio, mod_version, voice_credits

AUDIO = "Mods/DrovaVoice/Audio/de"


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "mod" / "DrovaVoice").mkdir(parents=True)
    (repo / "mod" / "DrovaVoice" / "DrovaVoiceMod.cs").write_text(
        '[assembly: MelonInfo(typeof(DrovaVoice.DrovaVoiceMod), "DrovaVoice", "1.2.3", "x")]\n',
        encoding="utf-8",
    )
    (repo / "casting").mkdir()
    (repo / "casting" / "fish_voices.yaml").write_text(
        "voices:\n"
        '  a: {id: "aaa", label: "Amtlich", gender: f, source: offiziell}\n'
        '  b: {id: "bbb", label: "Gemeinschaft", gender: m, source: bibliothek}\n',
        encoding="utf-8",
    )
    (repo / "release").mkdir()
    (repo / "release" / "README.txt").write_text(
        "Version {version}, {entries} Zeilen, {language}\n", encoding="utf-8"
    )
    (repo / "release" / "LIZENZEN.txt").write_text("{voices}", encoding="utf-8")
    return repo


def _game(tmp_path, entries):
    game = tmp_path / "game"
    for rel in ("Mods/DrovaVoice.dll", "UserLibs/DrovaVoice.Core.dll", "UserLibs/NVorbis.dll"):
        (game / rel).parent.mkdir(parents=True, exist_ok=True)
        (game / rel).write_bytes(b"DLL")
    audio = game / AUDIO
    (audio / "dialog").mkdir(parents=True)
    (audio / "index.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return game, audio


def test_package_holds_mod_libraries_texts_and_only_indexed_audio(tmp_path):
    repo = _repo(tmp_path)
    game, audio = _game(
        tmp_path,
        {
            "T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0},
            "T|P|Plh_1#vm1": {"file": "dialog/a.ogg", "duration": 1.0},
        },
    )
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    (audio / "dialog" / "verwaist.ogg").write_bytes(b"OLD")
    (game / "Mods" / "DrovaVoice" / "Export").mkdir()
    (game / "Mods" / "DrovaVoice" / "Export" / "manifest.json").write_text("{}", encoding="utf-8")

    result = build_package(game, "de", repo, tmp_path / "dist")

    assert result.path.name == "DrovaVoice-1.2.3-de.zip"
    assert result.audio_files == 1 and result.entries == 2
    with zipfile.ZipFile(result.path) as zf:
        names = set(zf.namelist())
        readme = zf.read("README.txt").decode("utf-8-sig")
        credits = zf.read("LIZENZEN.txt").decode("utf-8-sig")
        assert zf.getinfo(f"{AUDIO}/dialog/a.ogg").compress_type == zipfile.ZIP_STORED
    assert names == {
        "README.txt",
        "LIZENZEN.txt",
        "Mods/DrovaVoice.dll",
        "UserLibs/DrovaVoice.Core.dll",
        "UserLibs/NVorbis.dll",
        f"{AUDIO}/index.json",
        f"{AUDIO}/dialog/a.ogg",
    }
    assert readme == "Version 1.2.3, 2 Zeilen, de\r\n"
    assert "Amtlich" in credits and "https://fish.audio/m/bbb" in credits
    sha = result.path.with_name(result.path.name + ".sha256").read_text(encoding="utf-8")
    assert sha.startswith(result.sha256)


def test_same_input_gives_the_same_zip(tmp_path):
    repo = _repo(tmp_path)
    game, audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    first = build_package(game, "de", repo, tmp_path / "one").sha256
    assert build_package(game, "de", repo, tmp_path / "two").sha256 == first


def test_missing_audio_file_stops_the_package(tmp_path):
    repo = _repo(tmp_path)
    game, _ = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/fehlt.ogg", "duration": 1.0}})
    with pytest.raises(ValueError, match="fehlt"):
        build_package(game, "de", repo, tmp_path / "dist")
    assert not (tmp_path / "dist" / "DrovaVoice-1.2.3-de.zip").exists()


@pytest.mark.parametrize(
    "rel", ["../draussen.ogg", "/abs.ogg", "C:/win.ogg", "dialog\\a.ogg", None]
)
def test_unsafe_index_paths_are_rejected(tmp_path, rel):
    _, audio = _game(tmp_path, {"T|P|Plh_1": {"file": rel, "duration": 1.0}})
    with pytest.raises(ValueError, match="ungültiger Pfad"):
        indexed_audio(audio)


def test_missing_library_names_the_build_flag(tmp_path):
    repo = _repo(tmp_path)
    game, _ = _game(tmp_path, {})
    (game / "UserLibs" / "NVorbis.dll").unlink()
    with pytest.raises(ValueError, match="DeployToGame"):
        build_package(game, "de", repo, tmp_path / "dist")


def test_version_and_credits_come_from_the_repo(tmp_path):
    repo = _repo(tmp_path)
    assert mod_version(repo) == "1.2.3"
    text = voice_credits(repo / "casting" / "fish_voices.yaml")
    assert text.index("Amtlich") < text.index("Gemeinschaft")
