from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_START_RE = re.compile(r"^(.+?)\s*\{\s?(.*)$")
_BRACE_LINE_RE = re.compile(r"^\s*\{\s*$")
_HEADER_RE = re.compile(r"^\S[^{}]*\s\{(\s|$|\})")


@dataclass(frozen=True)
class LocEntry:
    key: str
    text: str
    line: int


@dataclass(frozen=True)
class LocParseResult:
    entries: tuple[LocEntry, ...]
    errors: tuple[int, ...]


def _starts_entry(lines: list[str], idx: int) -> bool:
    """True if lines[idx] looks like a new entry header rather than body text."""
    line = lines[idx].strip()
    if _HEADER_RE.match(line):
        return True
    # Key-only layout: a text line directly followed by a lone "{" line.
    return bool(line) and idx + 1 < len(lines) and bool(_BRACE_LINE_RE.match(lines[idx + 1]))


def parse_loc(content: str) -> LocParseResult:
    entries: list[LocEntry] = []
    errors: list[int] = []
    lines = content.lstrip("\ufeff").splitlines()
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
        while (
            j < len(lines) and not _starts_entry(lines, j) and not lines[j].rstrip().endswith("}")
        ):
            buffer.append(lines[j])
            j += 1
        if j >= len(lines) or _starts_entry(lines, j):
            # Unterminated entry: report its start and resume at the next header.
            errors.append(start)
            i = j
            continue
        buffer.append(lines[j].rstrip()[:-1])
        entries.append(LocEntry(key, "\n".join(part.strip() for part in buffer).strip(), start))
        i = j + 1
    return LocParseResult(tuple(entries), tuple(errors))


def read_loc_file(path: Path) -> LocParseResult:
    path = Path(path)
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeError as e:
        # Kein errors=replace: ein einzelnes Latin-1-Byte würde sonst still zu U+FFFD und so vertont.
        raise ValueError(
            f"{path}: Datei ist kein gültiges UTF-8 ({getattr(e, 'reason', e)})"
        ) from None
    return parse_loc(content)


def loc_rel_path(lang_dir: Path, file: Path, language: str) -> str:
    rel = Path(file).relative_to(lang_dir).as_posix()
    suffix = f"_{language}.loc"
    if rel.endswith(suffix):
        return rel[: -len(suffix)]
    return rel.removesuffix(".loc")
