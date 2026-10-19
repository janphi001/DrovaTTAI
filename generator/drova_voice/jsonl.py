from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable


def replace_with_retry(tmp: Path, path: Path, attempts: int = 40, delay: float = 0.25) -> None:
    # Windows: os.replace scheitert mit PermissionError, solange ein anderes Programm (Editor, Virenscanner,
    # ein Fortschritts-Check) die Zieldatei offen hat. Kurz warten und erneut versuchen.
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    # Erst in eine .tmp-Datei schreiben, dann ersetzen: bricht das Schreiben ab, bleibt die alte Datei erhalten.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_jsonl(path: Path) -> list[dict]:
    # utf-8-sig toleriert ein BOM am Dateianfang.
    # Nur "\n" als Trennzeichen: str.splitlines() würde auch U+2028/U+2029/U+0085 splitten,
    # die json.dumps(ensure_ascii=False) roh schreibt.
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").split("\n") if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    # Anhängen statt neu schreiben: Ein Abbruch kostet höchstens die letzte (halbe) Zeile.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "a+b") as f:
        f.seek(0, os.SEEK_END)
        if f.tell() > 0:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":  # halbe Zeile eines abgebrochenen Laufs: beenden, damit die neue Zeile gültig bleibt
                data = b"\n" + data
        f.write(data)


def read_jsonl_counted(path: Path) -> tuple[list[dict], int]:
    """Wie read_jsonl_lenient, zählt zusätzlich die nicht leeren Zeilen, die übersprungen wurden (kein gültiges JSON,
    kein Objekt, nicht lesbar). Fehlende Datei -> ([], 0)."""
    path = Path(path)
    if not path.exists():
        return [], 0
    rows = []
    skipped = 0
    for raw in path.read_bytes().split(b"\n"):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            skipped += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            skipped += 1
    return rows, skipped


def read_jsonl_lenient(path: Path) -> list[dict]:
    """Wie read_jsonl, aber: fehlende Datei -> [], nicht lesbare Zeilen (z. B. abgebrochenes Schreiben, auch mitten in
    einem Umlaut) werden übersprungen."""
    return read_jsonl_counted(path)[0]


def latest_by_id(rows: Iterable[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows if "id" in row}
