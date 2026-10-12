from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drova_voice.ids import normalize_loca_path
from drova_voice.loc import parse_loc


def in_scope(rel: Path) -> bool:
    """Umfang laut Spec §5: Dialog*/ (inkl. Dialogues/), sowie *World*.loc."""
    return rel.parts[0].startswith("Dialog") or "World" in rel.name


def loca_path_of(file: Path, loc_dir: Path, language: str) -> str:
    rel = file.relative_to(loc_dir).with_suffix("").as_posix()
    suffix = f"_{language}"
    if rel.endswith(suffix):
        rel = rel[: -len(suffix)]
    return normalize_loca_path(rel)


@dataclass(frozen=True)
class Coverage:
    total: int
    covered: int
    missing: tuple[str, ...]
    extra: int
    by_folder: dict[str, tuple[int, int]]
    unreadable: int = 0

    @property
    def percent(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 100.0


def compute_coverage(manifest: dict, loc_dir: Path, language: str) -> Coverage:
    in_manifest = {(normalize_loca_path(l["locaPath"]), l["locaKey"]) for l in manifest.get("lines", [])}
    wanted: set[tuple[str, str]] = set()
    folder_of: dict[tuple[str, str], str] = {}
    unreadable: list[tuple[str, str]] = []  # (Ordner, Bezeichnung) je unlesbarem Eintrag
    for file in sorted(Path(loc_dir).rglob("*.loc")):
        rel = file.relative_to(loc_dir)
        if not in_scope(rel):
            continue
        path = loca_path_of(file, loc_dir, language)
        folder = rel.parts[0] if len(rel.parts) > 1 else "(Wurzel)"
        result = parse_loc(file.read_text(encoding="utf-8-sig", errors="replace"))
        for entry in result.entries:
            wanted.add((path, entry.key))
            folder_of[(path, entry.key)] = folder
        for line in result.errors:  # unlesbar = nicht abgedeckt, zählt in Zähler und Nenner
            unreadable.append((folder, f"{path}:unlesbar, Zeile {line}"))
    missing = tuple([f"{p}:{k}" for p, k in sorted(wanted - in_manifest)] + sorted(label for _, label in unreadable))
    by_folder: dict[str, tuple[int, int]] = {}
    for item in wanted:
        total, covered = by_folder.get(folder_of[item], (0, 0))
        by_folder[folder_of[item]] = (total + 1, covered + (item in in_manifest))
    for folder, _ in unreadable:
        total, covered = by_folder.get(folder, (0, 0))
        by_folder[folder] = (total + 1, covered)
    return Coverage(
        total=len(wanted) + len(unreadable),
        covered=len(wanted & in_manifest),
        missing=missing,
        extra=len(in_manifest - wanted),
        by_folder=by_folder,
        unreadable=len(unreadable),
    )


def format_report(cov: Coverage, missing_path: Path) -> str:
    lines = [f"Abdeckung: {cov.percent:.2f} % ({cov.covered} von {cov.total} Einträgen im Manifest)",
             f"Zeilen im Manifest ohne .loc-Eintrag: {cov.extra}",
             f"Unlesbare Einträge (zählen als fehlend): {cov.unreadable}"]
    for folder, (total, covered) in sorted(cov.by_folder.items()):
        lines.append(f"  {folder}: {covered} von {total}")
    lines.append(f"Fehlende Einträge ({len(cov.missing)}): {missing_path}")
    return "\n".join(lines)
