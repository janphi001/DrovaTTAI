from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from drova_voice.ids import normalize_loca_path
from drova_voice.loc import read_loc_file

MAX_EXAMPLES = 5
TOP_COMBINATIONS = 15
MAX_LABEL = 40
FULL_MANIFEST = "manifest.json"
LOADED_MANIFEST = "manifest-loaded.json"


def locate_manifest(
    directory: Path, explicit: Path | None = None
) -> tuple[Path | None, str | None]:
    """(Pfad, Hinweis). None und die Fehlermeldung, wenn die Datei fehlt. Der Hinweis steht nur beim Ausweichen auf manifest-loaded.json."""
    if explicit is not None:
        path = Path(explicit)
        if path.is_file():
            return path, None
        return (
            None,
            f"Manifest nicht gefunden: {path} (Export im Spiel auslösen, siehe docs/export.md)",
        )
    directory = Path(directory)
    full, loaded = directory / FULL_MANIFEST, directory / LOADED_MANIFEST
    if full.is_file():
        return full, None
    if loaded.is_file():
        return loaded, f"Manifest: {loaded} ({FULL_MANIFEST} fehlt)"
    return None, (
        f"Manifest nicht gefunden: {full} (oder {loaded.name}; Export im Spiel auslösen, siehe docs/export.md)"
    )


def _norm(text: object) -> str:
    return " ".join(str(text).split())


def _label(value: object) -> str:
    text = str(value) if value else "-"
    return text if len(text) <= MAX_LABEL else text[: MAX_LABEL - 1] + "…"


def in_scope(rel: Path) -> bool:
    """Umfang laut Spec §5: Dialog*/ (inkl. Dialogues/), sowie *World*.loc."""
    return rel.parts[0].startswith("Dialog") or "World" in rel.name


def loca_path_of(file: Path, loc_dir: Path, language: str) -> str:
    rel = file.relative_to(loc_dir).with_suffix("").as_posix()
    suffix = f"_{language}"
    rel = rel.removesuffix(suffix)
    return normalize_loca_path(rel)


@dataclass(frozen=True)
class Coverage:
    total: int
    covered: int
    missing: tuple[str, ...]
    extra: int
    by_folder: dict[str, tuple[int, int]]
    unreadable: int = 0
    # Nur Information, ohne Einfluss auf Prozent und Exit-Code.
    text_checked: int = 0  # Manifest-Zeilen mit .loc-Eintrag, deren Text verglichen wurde
    text_mismatch: int = 0
    text_mismatch_examples: tuple[
        str, ...
    ] = ()  # höchstens MAX_EXAMPLES Bezeichnungen "pfad:schlüssel", nie Text
    gvar_checked: int = 0  # abgedeckte Manifest-Zeilen, deren .loc-Text $GVAR: enthält
    gvar_missing: int = 0  # davon mit leerer gvars-Liste im Manifest
    lines_total: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_actor: tuple[
        tuple[tuple[str, str, str], int], ...
    ] = ()  # ((actorName, nodeType, category), Anzahl), die häufigsten
    player_lines: int = 0

    @property
    def percent(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 100.0


def compute_coverage(manifest: dict, loc_dir: Path, language: str) -> Coverage:
    in_manifest = {
        (normalize_loca_path(l["locaPath"]), l["locaKey"]) for l in manifest.get("lines", [])
    }
    wanted: set[tuple[str, str]] = set()
    folder_of: dict[tuple[str, str], str] = {}
    loc_text: dict[tuple[str, str], str] = {}
    unreadable: list[tuple[str, str]] = []  # (Ordner, Bezeichnung) je unlesbarem Eintrag
    for file in sorted(Path(loc_dir).rglob("*.loc")):
        rel = file.relative_to(loc_dir)
        if not in_scope(rel):
            continue
        path = loca_path_of(file, loc_dir, language)
        folder = rel.parts[0] if len(rel.parts) > 1 else "(Wurzel)"
        result = read_loc_file(file)
        for entry in result.entries:
            wanted.add((path, entry.key))
            folder_of[(path, entry.key)] = folder
            loc_text[(path, entry.key)] = entry.text
        for line in result.errors:  # unlesbar = nicht abgedeckt, zählt in Zähler und Nenner
            unreadable.append((folder, f"{path}:unlesbar, Zeile {line}"))
    missing = tuple(
        [f"{p}:{k}" for p, k in sorted(wanted - in_manifest)]
        + sorted(label for _, label in unreadable)
    )
    by_folder: dict[str, tuple[int, int]] = {}
    for item in wanted:
        total, covered = by_folder.get(folder_of[item], (0, 0))
        by_folder[folder_of[item]] = (total + 1, covered + (item in in_manifest))
    for folder, _ in unreadable:
        total, covered = by_folder.get(folder, (0, 0))
        by_folder[folder] = (total + 1, covered)
    text_checked = text_mismatch = gvar_checked = gvar_missing = 0
    examples: list[str] = []
    categories: Counter[str] = Counter()
    combos: Counter[tuple[str, str, str]] = Counter()
    for l in manifest.get("lines", []):
        category = l.get("category") or "?"
        categories[category] += 1
        combos[(_label(l.get("actorName")), _label(l.get("nodeType")), _label(category))] += 1
        item = (normalize_loca_path(l["locaPath"]), l["locaKey"])
        if item not in loc_text:
            continue
        loc = loc_text[item]
        if "text" in l:
            text_checked += 1
            if _norm(l["text"]) != _norm(loc):
                text_mismatch += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append(f"{item[0]}:{item[1]}")
        if "$GVAR:" in loc:
            gvar_checked += 1
            if not l.get("gvars"):
                gvar_missing += 1
    return Coverage(
        total=len(wanted) + len(unreadable),
        covered=len(wanted & in_manifest),
        missing=missing,
        extra=len(in_manifest - wanted),
        by_folder=by_folder,
        unreadable=len(unreadable),
        text_checked=text_checked,
        text_mismatch=text_mismatch,
        text_mismatch_examples=tuple(examples),
        gvar_checked=gvar_checked,
        gvar_missing=gvar_missing,
        lines_total=sum(categories.values()),
        by_category=dict(categories),
        by_actor=tuple(sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_COMBINATIONS]),
        player_lines=categories.get("player", 0),
    )


def format_report(cov: Coverage, missing_path: Path) -> str:
    lines = [
        f"Abdeckung: {cov.percent:.2f} % ({cov.covered} von {cov.total} Einträgen im Manifest)",
        f"Zeilen im Manifest ohne .loc-Eintrag: {cov.extra}",
        f"Unlesbare Einträge (zählen als fehlend): {cov.unreadable}",
    ]
    for folder, (total, covered) in sorted(cov.by_folder.items()):
        lines.append(f"  {folder}: {covered} von {total}")
    lines.append(f"Fehlende Einträge ({len(cov.missing)}): {missing_path}")
    examples = (
        f" (Beispiele: {', '.join(cov.text_mismatch_examples)})"
        if cov.text_mismatch_examples
        else ""
    )
    lines.append(
        f"Text weicht von der .loc ab: {cov.text_mismatch} von {cov.text_checked}{examples}"
    )
    lines.append(
        f"$GVAR: in der .loc, aber leere gvars im Manifest: {cov.gvar_missing} von {cov.gvar_checked}"
    )
    if cov.lines_total:
        share = 100.0 * cov.player_lines / cov.lines_total
        lines.append(
            f"Manifest-Zeilen: {cov.lines_total}, davon player: {cov.player_lines} ({share:.1f} %)"
        )
        lines.append(
            "Je Kategorie: "
            + ", ".join(
                f"{c} {n}"
                for c, n in sorted(cov.by_category.items(), key=lambda kv: (-kv[1], kv[0]))
            )
        )
        lines.append(
            f"Häufigste Kombinationen (Sprecher | Knotentyp | Kategorie), {len(cov.by_actor)} von maximal {TOP_COMBINATIONS}:"
        )
        lines.extend(
            f"  {n:>7}  {actor} | {node_type} | {category}"
            for (actor, node_type, category), n in cov.by_actor
        )
    return "\n".join(lines)
