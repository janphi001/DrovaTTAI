import json

from drova_voice.cli import main
from drova_voice.lines import read_lines
from drova_voice.world_dialogues import (
    TEMPLATE_TREE,
    WorldArg,
    WorldModule,
    actor_for_entity,
    build_rows,
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
