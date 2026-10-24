import json
import sys
import types

from drova_voice.cli import main
from drova_voice.lines import read_lines
from drova_voice.world_dialogues import (
    TEMPLATE_TREE,
    WorldArg,
    WorldModule,
    _find_modules,
    _local_path_id,
    _owner,
    _read_names,
    _scan_bundle,
    actor_for_entity,
    build_rows,
    scan,
    write_rows,
)

NPCS = [{"entity": "EntityInfo_NPC_Testa", "name": "Testa", "locaKey": "Testa"}]
NAMES = {
    ("cab-a", 1): "EntityInfo_NPC_Testa",
    ("cab-a", 2): "EntityInfo_NPC_Probo",
    ("cab-a", 3): "EntityInfo_Player",
}


def module(*args, owner=None, graph="Dialog/Welt", uses_tree=False, perceptible=False):
    return WorldModule(
        graph=graph,
        args=tuple(WorldArg(*a) for a in args),
        owner=owner,
        uses_tree=uses_tree,
        perceptible=perceptible,
    )


def test_participant_wins_over_the_owner():
    npcs = [*NPCS, {"entity": "EntityInfo_NPC_Probo", "name": "Probo", "locaKey": "Probo"}]
    rows = build_rows(
        [module(("Dialog/Welt", "Plh_1", ("cab-a", 2)), owner=("cab-a", 1))], NAMES, npcs
    )
    assert rows[0]["actorName"] == "Probo"
    assert rows[0]["id"] == f"{TEMPLATE_TREE}|Dialog/Welt|Plh_1"
    assert rows[0]["category"] == "bark" and rows[0]["tree"] == TEMPLATE_TREE


def test_owner_speaks_without_participant_and_uses_the_npc_loca_key():
    rows = build_rows([module(("Dialog/Welt", "Plh_2", None), owner=("cab-a", 1))], NAMES, NPCS)
    assert rows[0]["actorName"] == "Testa"


def test_objects_without_entity_are_player_thoughts_and_crimes_are_generic():
    rows = build_rows(
        [
            module(("Dialog/Welt", "Plh_3", None)),
            module(("CrimesReactions", "Taschen", None), graph="CrimesReactions"),
        ],
        NAMES,
        NPCS,
    )
    by_key = {r["locaKey"]: r for r in rows}
    assert by_key["Plh_3"]["actorName"] == "Player" and by_key["Plh_3"]["category"] == "player"
    assert by_key["Taschen"]["actorName"] == "NPC" and by_key["Taschen"]["generic"] is True


def test_the_most_frequent_speaker_wins_a_shared_key():
    mods = [
        module(("Dialog/Welt", "Plh_4", ("cab-a", 2))),
        module(("Dialog/Welt", "Plh_4", ("cab-a", 1))),
        module(("Dialog/Welt", "Plh_4", ("cab-a", 1))),
    ]
    rows = build_rows(mods, NAMES, NPCS)
    assert len(rows) == 1 and rows[0]["actorName"] == "Testa"


def test_modules_with_their_own_tree_and_empty_keys_are_skipped():
    rows = build_rows(
        [module(("Dialog/Welt", "Plh_5", None), uses_tree=True), module(("Dialog/Welt", "", None))],
        NAMES,
        NPCS,
    )
    assert rows == []


def test_arg_path_falls_back_to_the_graph_path():
    rows = build_rows([module(("", "Plh_6", None), graph="Dialog/Anders")], NAMES, NPCS)
    assert rows[0]["locaPath"] == "Dialog/Anders"


def test_without_npc_list_the_name_is_guessed_from_the_asset():
    assert actor_for_entity("EntityInfo_NPC_Unbekannt", []) == "Unbekannt"
    assert actor_for_entity("EntityInfo_Player", []) == "Player"
    assert actor_for_entity(None, []) is None


def test_entities_unknown_to_the_npc_list_are_generic_and_spaces_do_not_matter():
    npcs = [*NPCS, {"entity": "EntityInfo_NPC_Testa 1", "name": "Testa", "locaKey": "Testa"}]
    assert actor_for_entity("EntityInfo_Bande_01", npcs) == "NPC"
    assert actor_for_entity("EntityInfo_NPC_Testa1", npcs) == "Testa"


def test_perceptible_objects_are_spoken_by_the_player_even_with_an_owner_entity():
    rows = build_rows(
        [module(("Dialog/Welt", "Plh_7", None), owner=("cab-a", 1), perceptible=True)], NAMES, NPCS
    )
    assert rows[0]["actorName"] == "Player"


def test_a_participant_still_speaks_on_a_perceptible_object():
    rows = build_rows(
        [module(("Dialog/Welt", "Plh_8", ("cab-a", 1)), perceptible=True)], NAMES, NPCS
    )
    assert rows[0]["actorName"] == "Testa"


def test_extract_reads_world_lines_and_takes_the_text_from_the_loc_files(pipeline_repo, capsys):
    export = pipeline_repo.data / "export" / "de"
    first = json.loads((export / "manifest.json").read_text(encoding="utf-8"))["lines"][0]
    rows = build_rows(
        [
            module(
                (first["locaPath"], first["locaKey"], None),
                owner=("cab-a", 1),
                graph=first["locaPath"],
            )
        ],
        NAMES,
        NPCS,
    )
    write_rows(export / "manifest-world.jsonl", rows)
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    world = [l for l in lines if l.tree == TEMPLATE_TREE]
    assert len(world) == 1 and world[0].actor == "Testa"
    assert world[0].speech == next(l.speech for l in lines if l.id == first["id"])
    assert "1 Welt-Dialog-Zeilen" in capsys.readouterr().out


def test_a_tie_goes_to_the_alphabetically_first_speaker():
    npcs = [*NPCS, {"entity": "EntityInfo_NPC_Probo", "name": "Probo", "locaKey": "Probo"}]
    rows = build_rows(
        [
            module(("Dialog/Welt", "Plh_9", ("cab-a", 1))),
            module(("Dialog/Welt", "Plh_9", ("cab-a", 2))),
        ],
        NAMES,
        npcs,
    )
    assert rows[0]["actorName"] == "Probo"


def test_an_unknown_asset_without_an_npc_list_keeps_its_name():
    assert actor_for_entity("Bandit_07", []) == "Bandit_07"


def test_find_modules_stops_on_a_cycle():
    node = {"_worldDialogueSettings": {"_graphLocaPath": "Dialog/Welt", "Args": []}}
    node["loop"] = node
    assert list(_find_modules(node)) == [node]
    assert list(_find_modules({"other": [1, "x", {"nope": True}]})) == []


def _local_ref(pointer):
    if not isinstance(pointer, dict):
        return None
    path_id = pointer.get("m_PathID")
    if path_id in (None, 0) or pointer.get("m_FileID", 0) != 0:
        return None
    return ["cab-a", path_id]


def test_local_pointers_reject_external_empty_and_non_dicts():
    assert _local_path_id("x") is None
    assert _local_path_id({"m_FileID": 2, "m_PathID": 5}) is None
    assert _local_path_id({"m_PathID": 0}) is None
    assert _local_path_id({"m_PathID": True}) is None
    assert _local_path_id({"m_FileID": 0, "m_PathID": 4}) == 4


def test_owner_follows_omitted_file_ids_and_skips_bad_components():
    cab = "cab-a"
    nodes = {
        (cab, 10): {
            "m_Name": "Kind",
            "m_Component": ["kaputt", None, {"component": {"m_PathID": 11}}],
        },
        (cab, 11): {"m_Father": {"m_PathID": 20}},
        (cab, 20): {"m_GameObject": {"m_PathID": 30}},
        (cab, 30): {
            "m_Name": "PerceptibleStatue",
            "m_Component": [{"component": {"m_FileID": 0, "m_PathID": 31}}],
        },
        (cab, 31): {"_entityInfo": {"m_FileID": 0, "m_PathID": 99}},
    }
    owner, chain = _owner({"m_GameObject": {"m_PathID": 10}}, cab, nodes.get, _local_ref)
    assert owner == ["cab-a", 99]
    assert chain == ["Kind", "PerceptibleStatue"]


def test_owner_stops_when_the_chain_breaks_or_runs_past_the_depth_limit():
    assert _owner({}, "cab-a", {}.get, _local_ref) == (None, [])
    assert _owner({"m_GameObject": {"m_PathID": 1}}, "cab-a", lambda key: "nope", _local_ref) == (
        None,
        [],
    )
    nodes = {
        ("cab-a", 1): {
            "m_Name": "A",
            "m_Component": [
                "kein-dict",
                {"component": {"m_FileID": 3, "m_PathID": 1}},
                {"component": {"m_PathID": 2}},
                {"component": {"m_PathID": 3}},
                {"component": {"m_PathID": 4}},
            ],
        },
        ("cab-a", 2): "kein-baum",
        ("cab-a", 3): {"m_Father": "kein-zeiger"},
        ("cab-a", 4): {"m_Father": {"m_PathID": 5}},
        ("cab-a", 5): "kein-transform",
    }
    owner, chain = _owner({"m_GameObject": {"m_PathID": 1}}, "cab-a", nodes.get, _local_ref)
    assert owner is None and chain == ["A"]
    owner, chain = _owner(
        {"m_GameObject": {"m_PathID": 8}},
        "cab-a",
        {("cab-a", 8): {"m_Name": "B", "m_Component": "text"}}.get,
        _local_ref,
    )
    assert owner is None and chain == ["B"]

    deep = {}
    for index in range(1, 20):
        deep[("cab-a", index)] = {
            "m_Name": f"E{index}",
            "m_Component": [{"component": {"m_PathID": 100 + index}}],
        }
        deep[("cab-a", 100 + index)] = {"m_Father": {"m_PathID": 200 + index}}
        deep[("cab-a", 200 + index)] = {"m_GameObject": {"m_PathID": index + 1}}
    owner, chain = _owner({"m_GameObject": {"m_PathID": 1}}, "cab-a", deep.get, _local_ref)
    assert owner is None and len(chain) == 12


def test_a_list_cycle_and_a_throwing_object_do_not_abort_the_bundle(monkeypatch):
    loop = []
    loop.append(loop)
    assert list(_find_modules(loop)) == []

    class _TypeBoom:
        def __init__(self):
            self.assets_file = _File("CAB-Alpha")
            self.path_id = 3

        @property
        def type(self):
            raise RuntimeError("typ")

    assets = _File("CAB-Alpha")
    module_tree = {
        "m_GameObject": {"m_PathID": 10},
        "_worldDialogueSettings": {
            "_graphLocaPath": 5,
            "Args": [
                {"_path": "Dialog/Welt", "_key": "Plh_1", "Participant": "nein"},
            ],
        },
        "nested": {
            "_worldDialogueSettings": {"_graphLocaPath": "Dialog/Welt", "Args": "keine-liste"},
        },
    }
    game_object = {"m_Name": "Kiste", "m_Component": []}

    def load(path):
        return _Env(
            [
                _TypeBoom(),
                _Obj(assets, 1, "MonoBehaviour", module_tree),
                _Obj(assets, 10, "GameObject", game_object),
                _Obj(assets, 9, "MonoBehaviour", {"m_Name": 5, "Participant": "nein"}),
            ]
        )

    _install_unity(monkeypatch, load)
    found, cabs = _scan_bundle("good.bundle")
    assert cabs == ["CAB-Alpha"] and len(found) == 2
    assert found[0]["graph"] == "" and found[0]["args"] == [["Dialog/Welt", "Plh_1", None]]
    assert found[1]["args"] == []
    names = _read_names(("good.bundle", [["CAB-Alpha", 9], ["CAB-Alpha", "nein"]]))
    assert names["cab-alpha|9"] == ""


class _Ext:
    def __init__(self, path):
        self.path = path


class _File:
    def __init__(self, name, externals=()):
        self.name = name
        self.externals = externals


class _Obj:
    def __init__(self, assets, path_id, type_name, tree):
        self.assets_file = assets
        self.path_id = path_id
        self.type = types.SimpleNamespace(name=type_name)
        self._tree = tree

    def read_typetree(self):
        if isinstance(self._tree, BaseException):
            raise self._tree
        return self._tree


class _Broken:
    assets_file = None
    path_id = None
    type = None


class _Env:
    def __init__(self, objects):
        self.objects = objects


def _install_unity(monkeypatch, load):
    module = types.ModuleType("UnityPy")
    module.load = load
    monkeypatch.setitem(sys.modules, "UnityPy", module)


def test_scan_bundle_reads_refs_and_keeps_the_module_when_an_object_is_broken(monkeypatch):
    cab = "CAB-Alpha"
    assets = _File(cab, externals=[_Ext("shared/CAB-Beta"), _Ext(None)])
    module_tree = {
        "m_GameObject": {"m_PathID": 10},
        "_useTree": 1,
        "_worldDialogueSettings": {
            "_graphLocaPath": "Dialog/Welt",
            "Args": [
                {
                    "_path": "Dialog/Welt",
                    "_key": "Plh_1",
                    "Participant": {"m_FileID": 1, "m_PathID": 7},
                },
                {"_path": "", "_key": "Plh_2", "Participant": {"m_PathID": 0}},
                {"_key": "Plh_3", "Participant": {"m_FileID": 9, "m_PathID": 1}},
                {"_key": "Plh_4", "Participant": {"m_FileID": 2, "m_PathID": 1}},
                "kein-dict",
                {
                    "_path": "Dialog/Welt",
                    "_key": "Plh_5",
                    "Participant": {"m_FileID": 0, "m_PathID": 12},
                },
            ],
        },
    }
    game_object = {
        "m_Name": "PerceptibleStatue",
        "m_Component": ["kaputt", {"component": {"m_PathID": 11}}],
    }
    entity = {"_entityInfo": {"m_FileID": 0, "m_PathID": 99}}
    _install_unity(monkeypatch, lambda path: _Env([]))
    found, cabs = _scan_bundle("ignored.bundle")
    assert found == [] and cabs == []

    def load(path):
        return _Env(
            [
                _Broken(),
                _Obj(assets, 1, "MonoBehaviour", module_tree),
                _Obj(assets, 10, "GameObject", game_object),
                _Obj(assets, 11, "MonoBehaviour", entity),
                _Obj(assets, 8, "MonoBehaviour", RuntimeError("defekt")),
                _Obj(assets, 2, "Texture2D", {"m_Name": "bild"}),
            ]
        )

    _install_unity(monkeypatch, load)
    found, cabs = _scan_bundle("good.bundle")
    assert cabs == [cab]
    assert len(found) == 1
    row = found[0]
    assert row["graph"] == "Dialog/Welt" and row["usesTree"] is True
    assert row["owner"] == [cab, 99] and row["perceptible"] is True
    assert [arg[2] for arg in row["args"]] == [["CAB-Beta", 7], None, None, None, [cab, 12]]


def test_scan_bundle_skips_a_bundle_that_will_not_load(monkeypatch):
    def load(path):
        raise RuntimeError(path)

    _install_unity(monkeypatch, load)
    assert _scan_bundle("kaputt.bundle") == ([], [])


def test_read_names_skips_a_broken_bundle_and_keeps_an_empty_name(monkeypatch):
    assets = _File("CAB-Beta")

    def load(path):
        if str(path).endswith("bad.bundle"):
            raise RuntimeError("kaputt")
        return _Env(
            [
                _Obj(assets, 7, "MonoBehaviour", {"m_Name": "EntityInfo_NPC_Testa"}),
                _Obj(assets, 8, "MonoBehaviour", RuntimeError("defekt")),
                _Broken(),
            ]
        )

    _install_unity(monkeypatch, load)
    assert _read_names(("bad.bundle", [["CAB-Beta", 7]])) == {}
    names = _read_names(("ok.bundle", [["CAB-Beta", 7], ["CAB-Beta", 8], ["nope", "x"]]))
    assert names["cab-beta|7"] == "EntityInfo_NPC_Testa"
    assert names["cab-beta|8"] == ""


def test_scan_resolves_a_name_in_another_bundle_and_skips_a_broken_one(tmp_path, monkeypatch):
    good = tmp_path / "good.bundle"
    other = tmp_path / "other.bundle"
    bad = tmp_path / "bad.bundle"
    for path in (good, other, bad):
        path.write_bytes(b"x")
    assets_a = _File("CAB-Alpha", externals=[_Ext("dir/CAB-Beta")])
    assets_b = _File("CAB-Beta")
    module_tree = {
        "m_GameObject": {"m_FileID": 0, "m_PathID": 10},
        "_worldDialogueSettings": {
            "_graphLocaPath": "Dialog/Welt",
            "Args": [
                {
                    "_path": "Dialog/Welt",
                    "_key": "Plh_1",
                    "Participant": {"m_FileID": 1, "m_PathID": 7},
                }
            ],
        },
    }
    game_object = {
        "m_Name": "Stall",
        "m_Component": [{"component": {"m_FileID": 0, "m_PathID": 11}}],
    }
    envs = {
        str(good): _Env(
            [
                _Obj(assets_a, 1, "MonoBehaviour", module_tree),
                _Obj(assets_a, 10, "GameObject", game_object),
                _Obj(assets_a, 11, "Transform", {"m_GameObject": {"m_FileID": 0, "m_PathID": 10}}),
            ]
        ),
        str(other): _Env([_Obj(assets_b, 7, "MonoBehaviour", {"m_Name": "EntityInfo_NPC_Testa"})]),
    }

    def load(path):
        if path == str(bad):
            raise RuntimeError("kaputt")
        return envs[path]

    _install_unity(monkeypatch, load)
    modules, names, count = scan(tmp_path, workers=1)
    assert count == 3 and len(modules) == 1
    assert modules[0].args[0].participant == ("cab-beta", 7)
    assert names[("cab-beta", 7)] == "EntityInfo_NPC_Testa"
    rows = build_rows(modules, names, NPCS)
    assert rows[0]["actorName"] == "Testa"


def test_scan_requires_unitypy_and_an_empty_folder_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "UnityPy", None)
    try:
        scan(tmp_path, workers=1)
    except RuntimeError as exc:
        assert "UnityPy fehlt" in str(exc)
    else:
        raise AssertionError("scan ohne UnityPy")
    module = types.ModuleType("UnityPy")
    module.load = lambda path: (_ for _ in ()).throw(AssertionError(path))
    monkeypatch.setitem(sys.modules, "UnityPy", module)
    assert scan(tmp_path, workers=0) == ([], {}, 0)


def _bundle_dir(game):
    path = game / "Drova_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
    path.mkdir(parents=True)
    return path


def test_export_world_writes_rows_and_passes_the_worker_count(pipeline_repo, monkeypatch, capsys):
    _bundle_dir(pipeline_repo.game)
    export = pipeline_repo.data / "export" / "de"
    (export / "npcs.json").write_text(json.dumps(NPCS), encoding="utf-8")
    seen = {}

    def fake(directory, workers=8):
        seen["workers"] = workers
        seen["name"] = directory.name
        return (
            [
                module(("Dialog/Welt", "Plh_8", None), uses_tree=True),
                module(("Dialog/Welt", "Plh_9", ("cab-a", 1))),
            ],
            NAMES,
            4,
        )

    monkeypatch.setattr("drova_voice.world_dialogues.scan", fake)
    code = main(["--config", str(pipeline_repo.cfg), "export", "world", "--workers", "2"])
    assert code == 0
    row = json.loads((export / "manifest-world.jsonl").read_text(encoding="utf-8"))
    assert row["locaKey"] == "Plh_9" and row["actorName"] == "Testa"
    out = capsys.readouterr().out
    assert "4 Bundles, 2 Welt-Dialog-Module (1 mit Vorlage): 1 Zeilen" in out
    assert seen == {"workers": 2, "name": "StandaloneWindows64"}


def test_export_world_reports_a_missing_bundle_folder(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "export", "world"]) == 2
    assert "Bundle-Ordner" in capsys.readouterr().err


def test_export_world_guesses_when_the_npc_list_is_missing_or_not_a_list(
    pipeline_repo, monkeypatch, capsys
):
    _bundle_dir(pipeline_repo.game)
    monkeypatch.setattr(
        "drova_voice.world_dialogues.scan",
        lambda directory, workers=8: (
            [module(("Dialog/Welt", "Plh_9", ("cab-a", 1)))],
            NAMES,
            1,
        ),
    )
    assert main(["--config", str(pipeline_repo.cfg), "export", "world"]) == 0
    assert "npcs.json fehlt" in capsys.readouterr().out
    export = pipeline_repo.data / "export" / "de"
    (export / "npcs.json").write_text('{"nein": true}', encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "export", "world"]) == 0
    assert "keine Liste" in capsys.readouterr().err
    row = json.loads((export / "manifest-world.jsonl").read_text(encoding="utf-8"))
    assert row["actorName"] == "Testa"


def test_export_world_fails_when_unitypy_is_missing(pipeline_repo, monkeypatch, capsys):
    _bundle_dir(pipeline_repo.game)
    monkeypatch.setitem(sys.modules, "UnityPy", None)
    assert main(["--config", str(pipeline_repo.cfg), "export", "world"]) == 2
    assert "UnityPy" in capsys.readouterr().err


def test_export_world_rejects_broken_npc_json(pipeline_repo, capsys):
    _bundle_dir(pipeline_repo.game)
    export = pipeline_repo.data / "export" / "de"
    (export / "npcs.json").write_text("{", encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "export", "world"]) == 2
    assert "JSONDecodeError" in capsys.readouterr().err
