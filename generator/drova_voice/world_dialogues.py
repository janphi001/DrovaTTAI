"""Welt-Dialoge aus den Addressables-Bundles des Spiels.

Viele Welt-Dialoge haben keinen eigenen Dialogbaum. Das Spiel baut sie zur Laufzeit aus dem
Vorlagen-Baum ``DT_WorldDialogue_Template``: ``WorldDialogueStarterModule`` hält
``_worldDialogueSettings`` (``_graphLocaPath`` und ``Args`` mit ``_path``, ``_key``, ``Participant``),
und ``SetNodes`` hängt je Arg einen Sprechknoten an. Der Export der Mod im Hauptmenü sieht diese
Zeilen nicht. Dieses Modul liest die Module direkt aus den Bundles (TypeTrees, über UnityPy) und
schreibt je Zeile eine Manifestzeile nach ``data/export/<Sprache>/manifest-world.jsonl``.

Sprecher, in dieser Reihenfolge:

1. ``Participant`` des Args.
2. Liegt das Modul auf einem Wahrnehmungs-Objekt (GameObject ``Perceptible…``/``PerceptableObject``),
   untersucht der Spieler etwas (Statue, Golem, Erzader …): Es spricht der Spieler, auch wenn das
   Objekt eine ``EntityInfo`` hat.
3. ``EntityInfo`` des Besitzers (Komponente mit ``_entityInfo`` auf dem GameObject oder darüber).
4. Ohne Besitzer: unter ``CrimesReactions`` ein beliebiger Zeuge, sonst der Spieler.

Eine ``EntityInfo``, die ``npcs.json`` nicht kennt (namenlose Banditen, Wachen), spricht als
generische Figur. Nutzen mehrere Module denselben Schlüssel mit verschiedenen Sprechern, gewinnt der
häufigste (bei Gleichstand der alphabetisch erste).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEMPLATE_TREE = "DT_WorldDialogue_Template"
OUTPUT_NAME = "manifest-world.jsonl"
PLAYER_ACTOR = "Player"
GENERIC_ACTOR = "NPC"
GENERIC_PATHS = frozenset({"CrimesReactions"})
OWNER_FIELDS = ("_entityInfo", "_entity", "_ownerEntityInfo")
MAX_DEPTH = 12
PERCEPTIBLE_PREFIXES = ("Perceptible", "Module_Perceptible", "PerceptableObject")

Ref = tuple[str, int]  # (Name der serialisierten Datei, z. B. "CAB-…", PathID)


@dataclass(frozen=True)
class WorldArg:
    path: str
    key: str
    participant: Ref | None


@dataclass(frozen=True)
class WorldModule:
    graph: str
    args: tuple[WorldArg, ...]
    owner: Ref | None
    uses_tree: bool = False
    perceptible: bool = False


def _norm(name: str) -> str:
    return name.replace(" ", "").lower()


def actor_for_entity(entity: str | None, npcs: Sequence[Mapping[str, Any]]) -> str | None:
    """Asset-Name einer EntityInfo (z. B. ``EntityInfo_NPC_Almar``) -> Sprechername wie im Spiel.

    Leerzeichen und Groß/klein zählen nicht (Asset ``…Gradan1``, ``npcs.json`` ``…Gradan 1``).
    Kennt ``npcs.json`` die Figur nicht, ist sie generisch; ohne ``npcs.json`` wird der Name
    aus dem Asset-Namen geraten.
    """
    if not entity:
        return None
    wanted = _norm(entity)
    for npc in npcs:
        if _norm(str(npc.get("entity", ""))) == wanted and isinstance(npc.get("locaKey"), str):
            return str(npc["locaKey"])
    if npcs:
        return GENERIC_ACTOR
    for prefix in ("EntityInfo_NPC_", "EntityInfo_"):
        if entity.startswith(prefix):
            return entity[len(prefix) :]
    return entity


def _speaker(
    module: WorldModule,
    arg: WorldArg,
    names: Mapping[Ref, str],
    npcs: Sequence[Mapping[str, Any]],
) -> str:
    if arg.participant:
        actor = actor_for_entity(names.get(arg.participant), npcs)
        if actor:
            return actor
    if module.perceptible:
        return PLAYER_ACTOR
    if module.owner:
        actor = actor_for_entity(names.get(module.owner), npcs)
        if actor:
            return actor
    path = arg.path or module.graph
    return GENERIC_ACTOR if path in GENERIC_PATHS else PLAYER_ACTOR


def build_rows(
    modules: Iterable[WorldModule],
    names: Mapping[Ref, str],
    npcs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Manifestzeilen (Felder wie im Export der Mod), sortiert nach ID."""
    votes: dict[tuple[str, str], Counter[str]] = {}
    for module in modules:
        if module.uses_tree:
            continue  # eigener Baum: steht schon im normalen Export
        for arg in module.args:
            if not arg.key:
                continue
            path = arg.path or module.graph
            votes.setdefault((path, arg.key), Counter())[_speaker(module, arg, names, npcs)] += 1
    rows = []
    for (path, key), counter in votes.items():
        actor = min(counter.items(), key=lambda item: (-item[1], item[0]))[0]
        rows.append(
            {
                "id": f"{TEMPLATE_TREE}|{path}|{key}",
                "tree": TEMPLATE_TREE,
                "nodeId": 0,
                "nodeType": "statement",
                "actorName": actor,
                "category": "player" if PLAYER_ACTOR.lower() in actor.lower() else "bark",
                "generic": actor == GENERIC_ACTOR,
                "locaPath": path,
                "locaKey": key,
                "text": "",  # kommt beim Extrahieren aus den .loc-Dateien
                "gvars": [],
                "next": [],
                "prev": [],
            }
        )
    return sorted(rows, key=lambda row: row["id"])


def write_rows(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# --- Lesen der Bundles (braucht UnityPy, optionales Extra "assets") ---------------------------


def _find_modules(node: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(node, dict):
        settings = node.get("_worldDialogueSettings")
        if isinstance(settings, dict):
            yield node
        for value in node.values():
            yield from _find_modules(value)
    elif isinstance(node, list):
        for value in node:
            yield from _find_modules(value)


def _scan_bundle(path: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Module eines Bundles (als JSON-taugliche dicts) und die Namen seiner serialisierten Dateien."""
    import UnityPy

    env = UnityPy.load(path)
    objects = {(obj.assets_file.name, obj.path_id): obj for obj in env.objects}
    cache: dict[Ref, Any] = {}

    def tree(key: Ref) -> Any:
        if key not in cache:
            obj = objects.get(key)
            try:
                cache[key] = obj.read_typetree() if obj is not None else None
            except Exception:  # noqa: BLE001  (UnityPy wirft beliebig; defekte Objekte überspringen)
                cache[key] = None
        return cache[key]

    found: list[dict[str, Any]] = []
    for (cab, pid), obj in objects.items():
        if obj.type.name != "MonoBehaviour":
            continue
        data = tree((cab, pid))
        if not isinstance(data, dict):
            continue
        modules = list(_find_modules(data))
        if not modules:
            continue
        externals = obj.assets_file.externals

        def ref(pointer: Any, cab: str = cab, externals: Any = externals) -> list[Any] | None:
            if not isinstance(pointer, dict) or not pointer.get("m_PathID"):
                return None
            fid = pointer.get("m_FileID", 0)
            if fid == 0:
                return [cab, pointer["m_PathID"]]
            try:
                return [os.path.basename(externals[fid - 1].path), pointer["m_PathID"]]
            except (IndexError, AttributeError):
                return None

        owner, chain = _owner(data, cab, tree, ref)
        perceptible = any(name.startswith(PERCEPTIBLE_PREFIXES) for name in chain)
        for module in modules:
            settings = module["_worldDialogueSettings"]
            found.append(
                {
                    "graph": settings.get("_graphLocaPath", "") or "",
                    "usesTree": bool(module.get("_useTree")),
                    "owner": owner,
                    "perceptible": perceptible,
                    "args": [
                        [
                            a.get("_path", "") or "",
                            a.get("_key", "") or "",
                            ref(a.get("Participant")),
                        ]
                        for a in settings.get("Args", []) or []
                        if isinstance(a, dict)
                    ],
                }
            )
    return found, sorted({name for name, _ in objects})


def _owner(
    data: Mapping[str, Any], cab: str, tree: Any, ref: Any
) -> tuple[list[Any] | None, list[str]]:
    """Nächste EntityInfo auf dem GameObject der Komponente oder darüber (nur im selben Bundle).

    Gibt auch die Namen der GameObjects bis dorthin zurück (für die Wahrnehmungs-Regel).
    """
    chain: list[str] = []
    go = data.get("m_GameObject") or {}
    key: Ref | None = (
        (cab, go["m_PathID"]) if go.get("m_FileID", 1) == 0 and go.get("m_PathID") else None
    )
    for _ in range(MAX_DEPTH):
        if key is None:
            return None, chain
        game_object = tree(key)
        if not isinstance(game_object, dict):
            return None, chain
        chain.append(str(game_object.get("m_Name", "")))
        parent: Ref | None = None
        for entry in game_object.get("m_Component", []) or []:
            pointer = (entry or {}).get("component") or {}
            if pointer.get("m_FileID", 1) != 0:
                continue
            component = tree((cab, pointer.get("m_PathID", 0)))
            if not isinstance(component, dict):
                continue
            for field in OWNER_FIELDS:
                hit = ref(component.get(field))
                if hit:
                    return hit, chain
            father = component.get("m_Father")
            if (
                isinstance(father, dict)
                and father.get("m_FileID", 1) == 0
                and father.get("m_PathID")
            ):
                transform = tree((cab, father["m_PathID"]))
                if isinstance(transform, dict):
                    up = transform.get("m_GameObject") or {}
                    if up.get("m_FileID", 1) == 0 and up.get("m_PathID"):
                        parent = (cab, up["m_PathID"])
        key = parent
    return None, chain


def _read_names(job: tuple[str, list[list[Any]]]) -> dict[str, str]:
    import UnityPy

    path, wanted = job
    keys = {(cab.lower(), int(pid)) for cab, pid in wanted}
    env = UnityPy.load(path)
    out: dict[str, str] = {}
    for obj in env.objects:
        if (obj.assets_file.name.lower(), obj.path_id) in keys:
            try:
                name = obj.read_typetree().get("m_Name", "")
            except Exception:  # noqa: BLE001  (defektes Objekt: Name bleibt leer)
                name = ""
            out[f"{obj.assets_file.name.lower()}|{obj.path_id}"] = name
    return out


def scan(bundle_dir: Path, workers: int = 8) -> tuple[list[WorldModule], dict[Ref, str], int]:
    """Alle Bundles lesen. Gibt Module, aufgelöste EntityInfo-Namen und die Zahl der Bundles zurück."""
    import multiprocessing

    try:
        import UnityPy  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "UnityPy fehlt. Installieren mit: pip install -e .[assets] (im Ordner generator)"
        ) from e
    files = sorted(str(p) for p in bundle_dir.glob("*.bundle"))
    raw: list[dict[str, Any]] = []
    cab_to_bundle: dict[str, str] = {}
    with multiprocessing.Pool(max(1, workers)) as pool:
        for path, (found, cabs) in zip(files, pool.imap(_scan_bundle, files, chunksize=4)):
            raw.extend(found)
            for cab in cabs:
                cab_to_bundle[cab.lower()] = path
        wanted: dict[str, list[list[Any]]] = {}
        for item in raw:
            refs = [a[2] for a in item["args"] if a[2]] + ([item["owner"]] if item["owner"] else [])
            for cab, pid in refs:
                bundle = cab_to_bundle.get(cab.lower())
                if bundle is not None:
                    wanted.setdefault(bundle, []).append([cab, pid])
        resolved: dict[str, str] = {}
        for part in pool.imap_unordered(_read_names, list(wanted.items())):
            resolved.update(part)
    names = {(k.rsplit("|", 1)[0], int(k.rsplit("|", 1)[1])): v for k, v in resolved.items()}

    def as_ref(value: Any) -> Ref | None:
        return (str(value[0]).lower(), int(value[1])) if value else None

    modules = [
        WorldModule(
            graph=item["graph"],
            uses_tree=item["usesTree"],
            perceptible=item["perceptible"],
            owner=as_ref(item["owner"]),
            args=tuple(WorldArg(a[0], a[1], as_ref(a[2])) for a in item["args"]),
        )
        for item in raw
    ]
    return modules, names, len(files)
