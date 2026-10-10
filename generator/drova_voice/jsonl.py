from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    # Nur "\n" als Trennzeichen: str.splitlines() würde auch U+2028/U+2029/U+0085 splitten,
    # die json.dumps(ensure_ascii=False) roh schreibt.
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").split("\n") if line.strip()]
