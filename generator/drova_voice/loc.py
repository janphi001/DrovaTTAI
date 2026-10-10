from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_START_RE = re.compile(r"^(.+?)\s*\{\s?(.*)$")
_BRACE_LINE_RE = re.compile(r"^\s*\{")


@dataclass(frozen=True)
class LocEntry:
    key: str
    text: str
    line: int


@dataclass(frozen=True)
class LocParseResult:
    entries: tuple[LocEntry, ...]
    errors: tuple[int, ...]


def parse_loc(content: str) -> LocParseResult:
    entries: list[LocEntry] = []
    errors: list[int] = []
    lines = content.lstrip("﻿").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        header, consumed = line, 1
        m = _START_RE.match(header)
        if not m and i + 1 < len(lines) and _BRACE_LINE_RE.match(lines[i + 1]):
            # Key on its own line, opening brace on the next line.
            header = f"{line.strip()} {lines[i + 1].strip()}"
            m = _START_RE.match(header)
            consumed = 2
        if not m:
            errors.append(i + 1)
            i += 1
            continue
        key, rest = m.group(1).strip(), m.group(2)
        start = i + 1
        if rest.rstrip().endswith("}"):
            entries.append(LocEntry(key, rest.rstrip()[:-1].strip(), start))
            i += consumed
            continue
        buffer = [rest]
        j = i + consumed
        while j < len(lines) and not lines[j].rstrip().endswith("}"):
            buffer.append(lines[j])
            j += 1
        if j >= len(lines):
            errors.append(start)
            break
        buffer.append(lines[j].rstrip()[:-1])
        entries.append(LocEntry(key, "\n".join(buffer).strip(), start))
        i = j + 1
    return LocParseResult(tuple(entries), tuple(errors))


def read_loc_file(path: Path) -> LocParseResult:
    return parse_loc(Path(path).read_text(encoding="utf-8-sig"))


def loc_rel_path(lang_dir: Path, file: Path, language: str) -> str:
    rel = Path(file).relative_to(lang_dir).as_posix()
    suffix = f"_{language}.loc"
    if rel.endswith(suffix):
        return rel[: -len(suffix)]
    return rel[: -len(".loc")] if rel.endswith(".loc") else rel
