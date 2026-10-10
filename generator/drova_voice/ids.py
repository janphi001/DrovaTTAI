from __future__ import annotations

import hashlib

SEP = "|"
VARIANT_SEP = "#"


def normalize_loca_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _require_clean(value: str, name: str) -> None:
    if SEP in value or VARIANT_SEP in value:
        raise ValueError(f"{name} darf weder '{SEP}' noch '{VARIANT_SEP}' enthalten: {value!r}")


def statement_id(tree: str, loca_path: str, loca_key: str) -> str:
    path = normalize_loca_path(loca_path)
    for value, name in ((tree, "tree"), (path, "loca_path"), (loca_key, "loca_key")):
        _require_clean(value, name)
    return SEP.join((tree, path, loca_key))


def choice_id(tree: str, loca_path: str, loca_key: str, choice_index: int) -> str:
    if choice_index < 0:
        raise ValueError(f"choice_index muss >= 0 sein: {choice_index}")
    return f"{statement_id(tree, loca_path, loca_key)}{SEP}c{choice_index}"


def with_variant(line_id: str, variant: str | None) -> str:
    if not variant:
        return line_id
    _require_clean(variant, "variant")
    return f"{line_id}{VARIANT_SEP}{variant}"


def audio_filename(full_id: str) -> str:
    return hashlib.sha1(full_id.encode("utf-8")).hexdigest()[:16] + ".ogg"
