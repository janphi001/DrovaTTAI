from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from drova_voice.ids import VARIANT_SEP
from drova_voice.jsonl import replace_with_retry

INDEX_VERSION = 1


@dataclass
class InstallResult:
    copied: int = 0
    entries: int = 0
    errors: list[str] = field(default_factory=list)


def split_variant(full_id: str) -> tuple[str, str | None]:
    base, sep, variant = full_id.partition(VARIANT_SEP)
    return (base, variant) if sep else (full_id, None)


def _load_index(path: Path, language: str) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        index = json.loads(path.read_text(encoding="utf-8-sig"))
        if index.get("version") != INDEX_VERSION or index.get("language") != language:
            return {}
        return dict(index.get("entries", {}))
    except (json.JSONDecodeError, AttributeError, OSError):
        return {}  # kaputter Index: neu aufbauen, die Dateien bleiben liegen


def _same_file(src: Path, dst: Path) -> bool:
    if not dst.is_file():
        return False
    a, b = src.stat(), dst.stat()
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def install_audio(rows: Sequence[dict], audio_dir: Path, install_dir: Path, language: str) -> InstallResult:
    audio_dir, install_dir = Path(audio_dir), Path(install_dir)
    index_path = install_dir / "index.json"
    # frühere Einträge behalten, aber nur solche, deren Datei noch da ist
    entries = {i: e for i, e in _load_index(index_path, language).items() if (install_dir / e.get("file", "")).is_file()}
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
    return result
