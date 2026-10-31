import hashlib
import json
import re
import zipfile
from pathlib import Path

import pytest

from drova_voice.cli import main
from drova_voice.ids import choice_id, statement_id
from drova_voice.release import (
    AUDIO_STAMP,
    STUB_LIBRARY,
    build_package,
    indexed_audio,
    mod_version,
    voice_credits,
)

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
    (audio / "index.json").write_text(
        json.dumps({"version": 1, "language": "de", "entries": entries}),
        encoding="utf-8",
    )
    return game, audio


def _add_audio(game, language, entries, ogg=b"OGG"):
    audio = game / "Mods" / "DrovaVoice" / "Audio" / language
    (audio / "dialog").mkdir(parents=True, exist_ok=True)
    (audio / "dialog" / "a.ogg").write_bytes(ogg)
    (audio / "index.json").write_text(
        json.dumps({"version": 1, "language": language, "entries": entries}),
        encoding="utf-8",
    )
    return audio


def _english_readme(repo):
    (repo / "release" / "README.en.txt").write_text(
        "Version {version}, {entries} lines, {language}\n{origin_note}{fixture_note}{library_note}",
        encoding="utf-8",
    )


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
        stamp = zf.read(AUDIO_STAMP)
    assert names == {
        "README.txt",
        "LIZENZEN.txt",
        "Mods/DrovaVoice.dll",
        "UserLibs/DrovaVoice.Core.dll",
        "UserLibs/NVorbis.dll",
        AUDIO_STAMP,
        f"{AUDIO}/index.json",
        f"{AUDIO}/dialog/a.ogg",
    }
    assert stamp == b"de\n"
    assert result.gap == result.path.with_name("DrovaVoice-1.2.3-de.synth-gap.txt")
    assert result.gap.is_file()
    assert readme == "Version 1.2.3, 2 Zeilen, de\r\n"
    assert "Amtlich" in credits and "https://fish.audio/m/bbb" in credits
    sha = result.path.with_name(result.path.name + ".sha256").read_text(encoding="utf-8")
    assert sha == f"{result.sha256}  {result.path.name}\n"
    assert hashlib.sha256(result.path.read_bytes()).hexdigest() == result.sha256


def test_same_input_gives_the_same_zip(tmp_path):
    repo = _repo(tmp_path)
    game, audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    first = build_package(game, "de", repo, tmp_path / "one")
    second = build_package(game, "de", repo, tmp_path / "two")
    assert second.sha256 == first.sha256
    first.gap.write_text("AGAIN\n" + first.gap.read_text(encoding="utf-8"), encoding="utf-8")
    third = build_package(game, "de", repo, tmp_path / "one")
    assert third.sha256 == first.sha256
    assert "AGAIN" not in third.gap.read_text(encoding="utf-8")
    assert third.gap.read_text(encoding="utf-8").count("language: de") == 1


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
        indexed_audio(audio, "de")


def test_missing_library_names_the_build_flag(tmp_path):
    repo = _repo(tmp_path)
    game, _ = _game(tmp_path, {})
    (game / "UserLibs" / "NVorbis.dll").unlink()
    with pytest.raises(ValueError, match="DeployToGame"):
        build_package(game, "de", repo, tmp_path / "dist")
    assert not (game / "UserLibs" / "NVorbis.dll").exists()


def test_version_and_credits_come_from_the_repo(tmp_path):
    repo = _repo(tmp_path)
    assert mod_version(repo) == "1.2.3"
    text = voice_credits(repo / "casting" / "fish_voices.yaml")
    assert text.index("Amtlich") < text.index("Gemeinschaft")


def test_a_source_without_meloninfo_is_rejected(tmp_path):
    repo = _repo(tmp_path)
    (repo / "mod" / "DrovaVoice" / "DrovaVoiceMod.cs").write_text("class X {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="MelonInfo"):
        mod_version(repo)


def test_a_missing_or_empty_index_is_rejected(tmp_path):
    _, audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    (audio / "index.json").unlink()
    with pytest.raises(ValueError, match="zuerst"):
        indexed_audio(audio, "de")
    (audio / "index.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        indexed_audio(audio, "de")
    (audio / "index.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="keine Einträge"):
        indexed_audio(audio, "de")
    (audio / "index.json").write_text(
        '{"version": 1, "language": "de", "entries": {}}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="keine Einträge"):
        indexed_audio(audio, "de")


def _config(repo, game):
    gen = repo / "generator"
    gen.mkdir()
    cfg = gen / "config.yaml"
    cfg.write_text(
        f"game_dir: '{game.as_posix()}'\nlanguage: de\nrepo_root: '{repo.as_posix()}'\n",
        encoding="utf-8",
    )
    return cfg


def test_package_command_writes_the_zip_and_prints_the_hash(tmp_path, capsys):
    repo = _repo(tmp_path)
    game, audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    cfg = _config(repo, game)
    assert main(["--config", str(cfg), "package", "--version", "9.9.9"]) == 0
    out = capsys.readouterr().out
    assert "DrovaVoice-9.9.9-de.zip" in out and "SHA-256" in out
    assert (repo / "dist" / "DrovaVoice-9.9.9-de.zip").is_file()


def test_package_command_reports_a_broken_index(tmp_path, capsys):
    repo = _repo(tmp_path)
    game, audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    (audio / "index.json").write_text("{", encoding="utf-8")
    cfg = _config(repo, game)
    assert main(["--config", str(cfg), "package"]) == 2
    assert "JSON" in capsys.readouterr().err
    assert not (repo / "dist").exists()


def test_de_and_en_zips_share_dll_bytes_and_stamp_their_language(tmp_path):
    repo = _repo(tmp_path)
    _english_readme(repo)
    entries = {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}}
    game, audio = _game(tmp_path, entries)
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    _add_audio(game, "en", entries)
    de = build_package(game, "de", repo, tmp_path / "de")
    en = build_package(game, "en", repo, tmp_path / "en")
    with zipfile.ZipFile(de.path) as de_zip, zipfile.ZipFile(en.path) as en_zip:
        for rel in ("Mods/DrovaVoice.dll", "UserLibs/DrovaVoice.Core.dll", "UserLibs/NVorbis.dll"):
            assert de_zip.read(rel) == en_zip.read(rel) == b"DLL"
        assert de_zip.read(AUDIO_STAMP) == b"de\n"
        assert en_zip.read(AUDIO_STAMP) == b"en\n"


def test_package_writes_the_argument_stamp_not_the_tree_file(tmp_path):
    repo = _repo(tmp_path)
    _english_readme(repo)
    entries = {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}}
    game, _audio = _game(tmp_path, entries)
    _add_audio(game, "en", entries)
    marker = game / "Mods" / "DrovaVoice" / "Audio" / "language.txt"
    marker.write_bytes(b"de\n")
    result = build_package(game, "en", repo, tmp_path / "dist")
    with zipfile.ZipFile(result.path) as zf:
        assert zf.read(AUDIO_STAMP) == b"en\n"
    assert marker.read_bytes() == b"de\n"


def test_entry_counts_use_dot_for_german_and_comma_otherwise(tmp_path):
    repo = _repo(tmp_path)
    _english_readme(repo)
    entries = {f"T|P|Plh_{i}": {"file": "dialog/a.ogg", "duration": 1.0} for i in range(1000)}
    game, audio = _game(tmp_path, entries)
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    _add_audio(game, "en", entries)
    de = build_package(game, "de", repo, tmp_path / "de")
    en = build_package(game, "en", repo, tmp_path / "en")
    with zipfile.ZipFile(de.path) as zf:
        assert "1.000" in zf.read("README.txt").decode("utf-8-sig")
    with zipfile.ZipFile(en.path) as zf:
        text = zf.read("README.txt").decode("utf-8-sig")
        assert "1,000" in text
        assert "Fish Audio synthesized the lines." in text
        assert "The crate is empty." not in text
        assert "DeployToGame" not in text


@pytest.mark.parametrize(
    ("version", "language_field", "folder"),
    [
        (True, "de", "de"),
        (2, "de", "de"),
        (1.0, "de", "de"),
        ("1", "de", "de"),
        (1, "en", "de"),
    ],
)
def test_index_gate_leaves_no_zip(tmp_path, version, language_field, folder):
    repo = _repo(tmp_path)
    entries = {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}}
    game, audio = _game(tmp_path, entries)
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    (audio / "index.json").write_text(
        json.dumps(
            {
                "version": version,
                "language": language_field,
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "dist"
    with pytest.raises(ValueError, match="version|language"):
        build_package(game, folder, repo, out)
    assert list(out.glob("*.zip")) == []
    assert list(out.glob("*.part")) == []


def test_stamp_path_follows_the_mod_file_name():
    root = Path(__file__).resolve().parents[2]
    settings = (root / "mod" / "DrovaVoice.Core" / "VoiceSettings.cs").read_text(encoding="utf-8")
    match = re.search(r'PackagedLanguageFileName = "([^"]+)"', settings)
    assert match is not None
    assert AUDIO_STAMP.endswith("Audio/" + match.group(1))
    mod = (root / "mod" / "DrovaVoice" / "DrovaVoiceMod.cs").read_text(encoding="utf-8")
    assert 'CreateEntry("AudioLanguage", "de"' not in mod


def test_missing_readme_template_raises_and_leaves_no_zip(tmp_path):
    repo = _repo(tmp_path)
    entries = {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}}
    game, audio = _game(tmp_path, entries)
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    _add_audio(game, "en", entries)
    out = tmp_path / "dist"
    with pytest.raises(ValueError, match="README.en.txt"):
        build_package(game, "en", repo, out)
    assert list(out.glob("*.zip")) == []


def test_package_language_en_without_that_audio_leaves_no_zip(tmp_path, capsys):
    repo = _repo(tmp_path)
    game, _audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    cfg = _config(repo, game)
    before = cfg.read_text(encoding="utf-8")
    out = tmp_path / "dist"
    assert main(["--config", str(cfg), "package", "--language", "en", "--out", str(out)]) == 2
    assert cfg.read_text(encoding="utf-8") == before
    assert list(out.glob("*.zip")) == []
    assert capsys.readouterr().err


def test_libraries_without_fixture_exits_2(tmp_path, capsys):
    repo = _repo(tmp_path)
    game, audio = _game(tmp_path, {"T|P|Plh_1": {"file": "dialog/a.ogg", "duration": 1.0}})
    (audio / "dialog" / "a.ogg").write_bytes(b"OGG")
    cfg = _config(repo, game)
    out = tmp_path / "dist"
    assert (
        main(
            [
                "--config",
                str(cfg),
                "package",
                "--libraries",
                str(game),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert "fixture" in capsys.readouterr().err
    assert list(out.glob("*.zip")) == []


def test_fixture_package_writes_an_english_zip(tmp_path):
    root = Path(__file__).resolve().parents[2]
    out = tmp_path / "dist"
    missing = tmp_path / "missing-config.yaml"
    assert (
        main(
            [
                "--config",
                str(missing),
                "package",
                "--language",
                "en",
                "--fixture",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    zip_path = out / "DrovaVoice-0.3.1-en.zip"
    assert zip_path.is_file()
    fid = statement_id("DT_Fixture", "Dialog/Crate", "Plh_1")
    with zipfile.ZipFile(zip_path) as zf:
        index = json.loads(zf.read("Mods/DrovaVoice/Audio/en/index.json"))
        assert index["language"] == "en"
        assert index["version"] == 1 and not isinstance(index["version"], bool)
        assert fid in index["entries"]
        assert choice_id("DT_Fixture", "Dialog/Crate", "Plh_1", 0) != fid
        assert "|c" not in fid
        rel = index["entries"][fid]["file"]
        assert rel.startswith("dialog/")
        assert not rel.startswith("player/")
        assert zf.read(f"Mods/DrovaVoice/Audio/en/{rel}").startswith(b"OggS")
        assert zf.read(AUDIO_STAMP) == b"en\n"
        assert zf.read("Mods/DrovaVoice.dll") == STUB_LIBRARY
        readme = zf.read("README.txt").decode("utf-8-sig")
    assert "The crate is empty." in readme
    assert "packaging fixture" in readme
    assert "not the finished English voice set" in readme
    assert "Fish Audio synthesized the lines." not in readme
    assert "Mods/DrovaVoice.dll" in readme
    assert "UserLibs/DrovaVoice.Core.dll" in readme
    assert "UserLibs/NVorbis.dll" in readme
    assert "DeployToGame" in readme
    gap = zip_path.with_name("DrovaVoice-0.3.1-en.synth-gap.txt")
    text = gap.read_text(encoding="utf-8")
    assert "The crate is empty." in text
    assert "data/export/en/manifest.json is absent" in text
    assert "casting/fish_voices.yaml has no region en" in text
    assert "player_name greetings are German." in text
    assert "data/lines.jsonl" in text and "data/synth/results.jsonl" in text
    assert "data/encoded.jsonl" in text
    assert "FISH_API_KEY" in text
    sidecar = zip_path.with_name(zip_path.name + ".sha256").read_text(encoding="utf-8")
    assert sidecar == f"{hashlib.sha256(zip_path.read_bytes()).hexdigest()}  {zip_path.name}\n"
    assert not (root / "generator" / "config.yaml").exists()
    assert not (root / "data" / "lines.jsonl").exists()
    assert not (root / "data" / "synth" / "results.jsonl").exists()
    assert not (root / "data" / "encoded.jsonl").exists()
    assert not (root / "cache").exists()
