import json
import os

import pytest

from drova_voice.install import install_audio, split_variant


def _symlink(link, target, directory=False):
    # Windows legt Symlinks nur mit Entwicklermodus oder Adminrecht an.
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as e:
        pytest.skip(f"Symlink nicht erlaubt: {e}")


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
    result = install_audio(
        [
            row("T|P|Plh_1", "dialog/aaaa.ogg", 1.23456),
            row("T|P|Plh_2|c0", "player/default/bbbb.ogg"),
        ],
        audio,
        target,
        "de",
    )
    assert (result.copied, result.entries, result.errors) == (2, 2, [])
    assert (target / "dialog" / "aaaa.ogg").read_bytes() == b"OggS-Test"
    index = read_index(target)
    assert index["version"] == 1 and index["language"] == "de"
    assert index["entries"]["T|P|Plh_1"] == {"file": "dialog/aaaa.ogg", "duration": 1.235}
    assert (
        index["entries"]["T|P|Plh_2|c0"]["file"] == "player/default/bbbb.ogg"
        and index["variants"] == {}
    )


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
    install_audio(
        [
            row("DT_Bär|P|Plh_1#neutral", "dialog/aaaa.ogg"),
            row("DT_Bär|P|Plh_1#arden", "dialog/bbbb.ogg"),
        ],
        audio,
        target,
        "de",
    )
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
    install_audio(
        [row("T|P|Plh_1", "dialog/aaaa.ogg"), row("T|P|Plh_2#arden", "dialog/bbbb.ogg")],
        audio,
        target,
        "de",
    )
    install_audio([], audio, target, "de", drop_ids={"T|P|Plh_2"})  # Varianten gehören zur Basis-ID
    index = read_index(target)
    assert sorted(index["entries"]) == ["T|P|Plh_1"] and index["variants"] == {}


def test_drop_ids_with_a_variant_id_remove_exactly_that_entry(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg")
    make_audio(audio, "dialog/bbbb.ogg")
    install_audio(
        [row("T|P|Plh_1", "dialog/aaaa.ogg"), row("T|P|Plh_2#neutral", "dialog/bbbb.ogg")],
        audio,
        target,
        "de",
    )
    install_audio([], audio, target, "de", drop_ids={"T|P|Plh_2#neutral"})
    index = read_index(target)
    assert sorted(index["entries"]) == ["T|P|Plh_1"] and index["variants"] == {}


def test_replaced_audio_is_copied_when_size_and_mtime_match(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/aaaa.ogg", b"AAAA")
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    src = audio / "dialog" / "aaaa.ogg"
    dst = target / "dialog" / "aaaa.ogg"
    src.write_bytes(b"BBBB")
    os.utime(src, ns=(dst.stat().st_mtime_ns, dst.stat().st_mtime_ns))
    install_audio([row("T|P|Plh_1", "dialog/aaaa.ogg")], audio, target, "de")
    assert dst.read_bytes() == b"BBBB"


def test_null_entries_are_rebuilt_instead_of_crashing(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    target.mkdir(parents=True)
    (target / "index.json").write_text(
        '{"version": 1, "language": "de", "entries": null}\n', encoding="utf-8"
    )
    result = install_audio([], audio, target, "de")
    assert (result.copied, result.entries, result.errors) == (0, 0, [])
    assert read_index(target)["entries"] == {}


def test_non_string_file_field_is_dropped_without_crashing(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    (target / "dialog").mkdir(parents=True)
    (target / "dialog" / "aaaa.ogg").write_bytes(b"OggS-keep")
    (target / "dialog" / "bad.ogg").write_bytes(b"OggS-bad")
    index = {
        "version": 1,
        "language": "de",
        "entries": {
            "T|P|Plh_1": {"file": "dialog/aaaa.ogg", "duration": 1},
            "T|P|Plh_2": {"file": 12, "duration": 1},
            "T|P|Plh_3": {"file": None, "duration": 1},
            "T|P|Plh_4": {"file": ["dialog/bad.ogg"], "duration": 1},
            "T|P|Plh_5": {"duration": 1},
        },
    }
    (target / "index.json").write_text(json.dumps(index), encoding="utf-8")
    result = install_audio([], audio, target, "de")
    assert (result.copied, result.entries, result.errors, result.pruned) == (0, 1, [], [])
    assert list(read_index(target)["entries"]) == ["T|P|Plh_1"]
    assert (target / "dialog" / "bad.ogg").read_bytes() == b"OggS-bad"


def test_unreadable_index_is_rebuilt_instead_of_crashing(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    target.mkdir(parents=True)
    (target / "index.json").write_bytes(b"\xff\xfe{")
    result = install_audio([], audio, target, "de")
    assert (result.copied, result.entries, result.errors) == (0, 0, [])
    assert read_index(target)["entries"] == {}


def _seed_keep_and_orphan(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    make_audio(audio, "dialog/keep.ogg", b"KEEP")
    make_audio(audio, "dialog/drop.ogg", b"DROP")
    install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg"), row("T|P|Plh_2", "dialog/drop.ogg")],
        audio,
        target,
        "de",
    )
    stray = target / "bark" / "stray.ogg"
    stray.parent.mkdir()
    stray.write_bytes(b"STRAY")
    (target / "bark" / "note.txt").write_text("bleiben", encoding="utf-8")
    return audio, target


def test_without_prune_orphan_oggs_stay(tmp_path):
    audio, target = _seed_keep_and_orphan(tmp_path)
    result = install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg")], audio, target, "de", drop_ids={"T|P|Plh_2"}
    )
    assert result.pruned == []
    assert (target / "dialog" / "drop.ogg").read_bytes() == b"DROP"
    assert (target / "bark" / "stray.ogg").is_file()
    assert sorted(read_index(target)["entries"]) == ["T|P|Plh_1"]


def test_prune_deletes_only_unreferenced_oggs(tmp_path):
    audio, target = _seed_keep_and_orphan(tmp_path)
    result = install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg")],
        audio,
        target,
        "de",
        drop_ids={"T|P|Plh_2"},
        prune=True,
        audio_root=target.parent,
    )
    assert result.pruned == ["bark/stray.ogg", "dialog/drop.ogg"]
    assert result.errors == [] and result.entries == 1
    assert (target / "dialog" / "keep.ogg").read_bytes() == b"KEEP"
    assert not (target / "dialog" / "drop.ogg").exists()
    assert not (target / "bark" / "stray.ogg").exists()
    assert (target / "bark" / "note.txt").is_file()
    assert (audio / "dialog" / "drop.ogg").read_bytes() == b"DROP"


def _tree_bytes(root):
    if not root.exists():
        return None
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_prune_dry_run_lists_orphans_and_keeps_them(tmp_path):
    audio, target = _seed_keep_and_orphan(tmp_path)
    result = install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg")],
        audio,
        target,
        "de",
        drop_ids={"T|P|Plh_2"},
        prune=True,
        dry_run=True,
    )
    assert (result.copied, result.entries, result.pruned) == (
        0,
        1,
        ["bark/stray.ogg", "dialog/drop.ogg"],
    )
    assert (target / "dialog" / "drop.ogg").is_file() and (target / "bark" / "stray.ogg").is_file()
    assert sorted(read_index(target)["entries"]) == ["T|P|Plh_1", "T|P|Plh_2"]


def test_dry_run_leaves_the_target_byte_identical(tmp_path):
    audio, target = _seed_keep_and_orphan(tmp_path)
    make_audio(audio, "dialog/keep.ogg", b"NEU")
    make_audio(audio, "dialog/fresh.ogg", b"FRESH")
    before = _tree_bytes(target)
    result = install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg", 2.5), row("U|Q|Plh_9", "dialog/fresh.ogg", 3.25)],
        audio,
        target,
        "de",
        drop_ids={"T|P|Plh_2"},
        prune=True,
        dry_run=True,
    )
    assert (result.copied, result.entries, result.errors) == (2, 2, [])
    assert result.pruned == ["bark/stray.ogg", "dialog/drop.ogg"]
    assert _tree_bytes(target) == before
    assert not (target / "index.json.tmp").exists()
    assert not (target / "dialog" / "fresh.ogg").exists()
    assert (target / "dialog" / "keep.ogg").read_bytes() == b"KEEP"

    missing = tmp_path / "fehlt"
    empty = install_audio([row("T|P|Plh_1", "dialog/keep.ogg")], audio, missing, "de", dry_run=True)
    assert empty.copied == 1 and empty.entries == 1 and empty.pruned == []
    assert _tree_bytes(missing) is None


def test_dry_run_without_prune_lists_orphans(tmp_path):
    audio, target = _seed_keep_and_orphan(tmp_path)
    before = read_index(target)
    result = install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg")],
        audio,
        target,
        "de",
        drop_ids={"T|P|Plh_2"},
        dry_run=True,
    )
    assert result.pruned == ["bark/stray.ogg", "dialog/drop.ogg"]
    assert (target / "dialog" / "keep.ogg").is_file() and (target / "dialog" / "drop.ogg").is_file()
    assert read_index(target) == before


def test_rel_that_leaves_the_folder_is_not_copied(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "nest" / "Audio"
    audio.mkdir()
    source = tmp_path / "escaped.ogg"
    source.write_bytes(b"SECRET")
    escaped = tmp_path / "nest" / "escaped.ogg"
    result = install_audio([row("T|P|Plh_1", "../escaped.ogg")], audio, target, "de")
    assert result.copied == 0 and result.entries == 0 and result.errors
    assert "Plh_1" in result.errors[0]
    assert not escaped.exists()
    assert source.read_bytes() == b"SECRET"
    assert read_index(target)["entries"] == {}


def test_absolute_and_drive_rel_stay_out_of_the_index(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    absolute = tmp_path / "abs.ogg"
    absolute.write_bytes(b"ABS")
    result = install_audio(
        [row("T|P|Plh_1", absolute.as_posix()), row("T|P|Plh_2", "C:/Windows/note.ogg")],
        audio,
        target,
        "de",
    )
    assert result.copied == 0 and result.entries == 0 and len(result.errors) == 2
    assert absolute.read_bytes() == b"ABS"
    assert sorted(p.name for p in target.iterdir()) == [
        "index.json"
    ]  # unter Windows ist target / "C:" das Laufwerk
    assert read_index(target)["entries"] == {}


def test_symlink_outside_the_audio_folder_is_not_installed(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    outside = tmp_path / "outside"
    outside.mkdir()
    audio.mkdir()
    _symlink(audio / "link", outside, directory=True)
    (outside / "x.ogg").write_bytes(b"OUT")
    result = install_audio([row("T|P|Plh_1", "link/x.ogg")], audio, target, "de")
    assert result.copied == 0 and result.entries == 0 and result.errors
    assert (outside / "x.ogg").read_bytes() == b"OUT"
    assert list(outside.iterdir()) == [outside / "x.ogg"]


def test_backslash_file_field_still_protects_the_ogg(tmp_path):
    audio, target = tmp_path / "audio", tmp_path / "Audio" / "de"
    audio.mkdir()
    (target / "dialog").mkdir(parents=True)
    (target / "dialog" / "keep.ogg").write_bytes(b"KEEP")
    index = {
        "version": 1,
        "language": "de",
        "entries": {
            "T|P|Plh_1": {"file": "dialog\\keep.ogg", "duration": 1.0},
        },
    }
    (target / "index.json").write_text(json.dumps(index), encoding="utf-8")
    result = install_audio([], audio, target, "de", prune=True, audio_root=target.parent)
    assert result.pruned == [] and result.entries == 1
    assert (target / "dialog" / "keep.ogg").read_bytes() == b"KEEP"


def test_prune_without_an_audio_root_deletes_nothing(tmp_path):
    audio, target = _seed_keep_and_orphan(tmp_path)
    result = install_audio(
        [row("T|P|Plh_1", "dialog/keep.ogg")],
        audio,
        target,
        "de",
        drop_ids={"T|P|Plh_2"},
        prune=True,
    )
    assert result.pruned == [] and result.errors
    assert (target / "dialog" / "drop.ogg").read_bytes() == b"DROP"
    assert (target / "bark" / "stray.ogg").is_file()


def test_prune_does_not_delete_when_the_target_resolves_outside_the_audio_folder(tmp_path):
    game = tmp_path / "game"
    audio_root = game / "Mods" / "DrovaVoice" / "Audio"
    parent = audio_root.parent
    parent.mkdir(parents=True)
    secret = parent / "secret.ogg"
    secret.write_bytes(b"SECRET")
    src = tmp_path / "src"
    src.mkdir()
    result = install_audio(
        [], src, audio_root / "..", "de", prune=True, audio_root=audio_root, game_dir=game
    )
    assert result.pruned == [] and result.errors
    assert "nichts gelöscht" in result.errors[0]
    assert secret.read_bytes() == b"SECRET"


def test_prune_does_not_delete_when_the_language_path_resolves_to_the_audio_root(tmp_path):
    game = tmp_path / "game"
    audio_root = game / "Mods" / "DrovaVoice" / "Audio"
    audio_root.mkdir(parents=True)
    secret = audio_root / "secret.ogg"
    secret.write_bytes(b"SECRET")
    src = tmp_path / "src"
    src.mkdir()
    result = install_audio(
        [], src, audio_root / "de" / "..", "de", prune=True, audio_root=audio_root, game_dir=game
    )
    assert result.pruned == [] and result.errors
    assert secret.read_bytes() == b"SECRET"


def test_prune_does_not_follow_an_audio_folder_symlink_out_of_the_game(tmp_path):
    game = tmp_path / "game"
    mods = game / "Mods" / "DrovaVoice"
    mods.mkdir(parents=True)
    outside = tmp_path / "outside"
    (outside / "de").mkdir(parents=True)
    secret = outside / "de" / "secret.ogg"
    secret.write_bytes(b"SECRET")
    audio_root = mods / "Audio"
    _symlink(audio_root, outside, directory=True)
    src = tmp_path / "src"
    src.mkdir()
    result = install_audio(
        [], src, audio_root / "de", "de", prune=True, audio_root=audio_root, game_dir=game
    )
    assert result.pruned == [] and result.errors
    assert secret.read_bytes() == b"SECRET"


def test_prune_does_not_delete_through_a_symlink_to_an_outside_file(tmp_path):
    game = tmp_path / "game"
    audio_root = game / "Mods" / "DrovaVoice" / "Audio"
    target = audio_root / "de"
    (target / "dialog").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.ogg"
    secret.write_bytes(b"SECRET")
    link = target / "dialog" / "alias.ogg"
    _symlink(link, secret)
    stray = target / "dialog" / "stray.ogg"
    stray.write_bytes(b"STRAY")
    src = tmp_path / "src"
    src.mkdir()
    result = install_audio([], src, target, "de", prune=True, audio_root=audio_root, game_dir=game)
    assert secret.read_bytes() == b"SECRET" and link.is_symlink()
    assert not stray.exists()
    assert result.pruned == ["dialog/stray.ogg"]
    assert any("alias.ogg" in error for error in result.errors)
