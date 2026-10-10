from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    # Erst in eine .tmp-Datei schreiben, dann ersetzen: bricht das Schreiben ab, bleibt die alte Datei erhalten.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_jsonl(path: Path) -> list[dict]:
    # utf-8-sig toleriert ein BOM am Dateianfang.
    # Nur "\n" als Trennzeichen: str.splitlines() würde auch U+2028/U+2029/U+0085 splitten,
    # die json.dumps(ensure_ascii=False) roh schreibt.
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").split("\n") if line.strip()]
