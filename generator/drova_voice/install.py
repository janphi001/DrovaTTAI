from __future__ import annotations

import filecmp
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Collection, Sequence

from drova_voice.ids import VARIANT_SEP
from drova_voice.jsonl import replace_with_retry

INDEX_VERSION = 1


@dataclass
class InstallResult:
    copied: int = 0
    entries: int = 0
    errors: list[str] = field(default_factory=list)
    pruned: list[str] = field(default_factory=list)


def split_variant(full_id: str) -> tuple[str, str | None]:
    base, sep, variant = full_id.partition(VARIANT_SEP)
    return (base, variant) if sep else (full_id, None)


def _load_index(path: Path, language: str) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        index = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return {}
    if not isinstance(index, dict):
        return {}
    if index.get("version") != INDEX_VERSION or index.get("language") != language:
        return {}
    raw = index.get("entries", {})
    if not isinstance(raw, dict):
        return {}
    # file muss Text sein: eine Zahl, null oder eine Liste lässt sich nicht als Pfad anhängen.
    return {i: e for i, e in raw.items()
            if isinstance(i, str) and isinstance(e, dict) and isinstance(e.get("file"), str)}


def _same_file(src: Path, dst: Path) -> bool:
    if not dst.is_file():
        return False
    return filecmp.cmp(src, dst, shallow=False)


def _index_file(file: str) -> str:
    # Indexe können auf Windows mit Backslash geschrieben sein; der Ordner selbst nutzt '/'.
    return file.replace("\\", "/")


def _installed(install_dir: Path, entry: dict) -> bool:
    file = entry.get("file")
    if not isinstance(file, str) or not file:
        return False
    try:
        return (install_dir / _index_file(file)).is_file()
    except (OSError, ValueError):
        return False


def _referenced_files(entries: dict[str, dict]) -> set[str]:
    return {_index_file(entry["file"]) for entry in entries.values() if isinstance(entry.get("file"), str)}


def _orphan_oggs(install_dir: Path, entries: dict[str, dict]) -> list[str]:
    """OGG-Dateien unter install_dir, die kein Eintrag mehr nennt. Andere Dateien bleiben."""
    referenced = _referenced_files(entries)
    if not install_dir.is_dir():
        return []
    orphans = []
    for path in install_dir.rglob("*.ogg"):
        if not path.is_file():
            continue
        rel = path.relative_to(install_dir).as_posix()
        if rel not in referenced:
            orphans.append(rel)
    return sorted(orphans)


def _delete_orphans(install_dir: Path, rels: list[str], result: InstallResult) -> list[str]:
    deleted = []
    for rel in rels:
        try:
            (install_dir / rel).unlink()
        except FileNotFoundError:
            deleted.append(rel)
        except OSError as e:
            result.errors.append(f"{rel}: Löschen fehlgeschlagen ({e.strerror or e})")
        else:
            deleted.append(rel)
    return deleted


def install_audio(rows: Sequence[dict], audio_dir: Path, install_dir: Path, language: str,
                  drop_ids: Collection[str] = (), prune: bool = False, dry_run: bool = False) -> InstallResult:
    audio_dir, install_dir = Path(audio_dir), Path(install_dir)
    index_path = install_dir / "index.json"
    # frühere Einträge behalten, aber nur solche, deren Datei noch da ist
    entries = {i: e for i, e in _load_index(index_path, language).items() if _installed(install_dir, e)}
    # Zeilen, die jetzt nicht mehr installiert werden sollen (übersprungen, ohne Stimme, veraltet), verlieren ihren Eintrag
    # (Basis-ID entfernt alle Varianten, eine Varianten-ID nur diese)
    entries = {i: e for i, e in entries.items() if i not in drop_ids and split_variant(i)[0] not in drop_ids}
    result = InstallResult()
    for row in rows:
        src, dst = audio_dir / row["rel"], install_dir / row["rel"]
        if not src.is_file():
            result.errors.append(f"{row['id']}: Datei fehlt ({src})")
            continue
        if not _same_file(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            part = dst.with_name(f"{dst.stem}.part.ogg")
            shutil.copy2(src, part)
            replace_with_retry(part, dst)
            result.copied += 1
        entries[row["id"]] = {"file": row["rel"], "duration": round(float(row["duration"]), 3)}
    variants: dict[str, list[str]] = {}
    for full_id in entries:
        base, variant = split_variant(full_id)
        if variant:
            variants.setdefault(base, []).append(variant)
    index = {"version": INDEX_VERSION, "language": language, "entries": entries,
             "variants": {b: sorted(v) for b, v in variants.items()}}
    install_dir.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_name("index.json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    replace_with_retry(tmp, index_path)
    result.entries = len(entries)
    # Erst den Index schreiben, dann löschen: ein Abbruch lässt höchstens Dateien übrig, nie einen Eintrag ohne Datei.
    if prune or dry_run:
        result.pruned = _orphan_oggs(install_dir, entries)
        if prune and not dry_run:
            result.pruned = _delete_orphans(install_dir, result.pruned, result)
    return result
