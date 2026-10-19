"""Release-Paket für Spieler: Mod, Bibliotheken, Audio und Liesmich in einem ZIP.

Quelle ist der Spielordner, also genau das, was im Spiel getestet wurde. Ins Paket kommen nur
OGG-Dateien, auf die `index.json` zeigt; verwaiste Dateien und der Export-Ordner bleiben draußen.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

# Pfade relativ zum Spielordner, so landen sie auch im ZIP.
MOD_DLL = "Mods/DrovaVoice.dll"
CORE_DLL = "UserLibs/DrovaVoice.Core.dll"
NVORBIS_DLL = "UserLibs/NVorbis.dll"
LIBRARIES = (MOD_DLL, CORE_DLL, NVORBIS_DLL)
TEXTS = ("README.txt", "LIZENZEN.txt")
# Feste Zeit im ZIP: derselbe Inhalt ergibt dieselbe Datei.
_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
_VERSION = re.compile(r'MelonInfo\(\s*typeof\([^)]*\)\s*,\s*"DrovaVoice"\s*,\s*"([^"]+)"')


@dataclass(frozen=True)
class PackageResult:
    path: Path
    sha256: str
    audio_files: int
    entries: int
    size: int


def mod_version(repo_root: Path) -> str:
    source = Path(repo_root) / "mod" / "DrovaVoice" / "DrovaVoiceMod.cs"
    match = _VERSION.search(source.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{source}: keine MelonInfo-Version gefunden")
    return match.group(1)


def _safe_rel(rel: object) -> str | None:
    if not isinstance(rel, str) or not rel or "\\" in rel:
        return None
    path = PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    return path.as_posix()


def indexed_audio(audio_dir: Path) -> tuple[list[str], int]:
    """Dateien aus index.json (sortiert, ohne Doppelte) und die Zahl der Einträge. Fehlt eine, bricht es ab."""
    index_path = Path(audio_dir) / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{index_path} fehlt (zuerst `drova-voice install`)") from None
    except json.JSONDecodeError as e:
        raise ValueError(f"{index_path}: kein gültiges JSON ({e})") from None
    entries = index.get("entries") if isinstance(index, dict) else None
    if not isinstance(entries, dict) or not entries:
        raise ValueError(f"{index_path}: keine Einträge")
    files: set[str] = set()
    problems: list[str] = []
    for line_id, entry in entries.items():
        rel = _safe_rel(entry.get("file") if isinstance(entry, dict) else None)
        if rel is None:
            problems.append(f"{line_id}: ungültiger Pfad")
        elif not (Path(audio_dir) / rel).is_file():
            problems.append(f"{line_id}: {rel} fehlt")
        else:
            files.add(rel)
    if problems:
        shown = "; ".join(problems[:10])
        raise ValueError(f"{len(problems)} Einträge ohne Datei in {index_path}: {shown}")
    return sorted(files), len(entries)


def voice_credits(catalog_path: Path) -> str:
    """Stimmenliste für LIZENZEN.txt: offizielle Fish-Stimmen und Bibliotheksstimmen mit Link."""
    raw = yaml.safe_load(Path(catalog_path).read_text(encoding="utf-8")) or {}
    voices = raw.get("voices") or {}
    official, library = [], []
    for voice in voices.values():
        label, voice_id = voice.get("label", "?"), voice.get("id", "")
        if voice.get("source") == "offiziell":
            official.append(f"  - {label}")
        else:
            library.append(f"  - {label}: https://fish.audio/m/{voice_id}")
    return (
        "Offizielle Stimmen von Fish Audio:\n"
        + "\n".join(official)
        + "\n\nStimmen aus der öffentlichen Fish-Audio-Bibliothek (Community-Autoren):\n"
        + "\n".join(library)
        + "\n"
    )


def _text(template: Path, values: dict[str, str]) -> bytes:
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    # Windows-Zeilenenden: Notepad zeigt die Datei sonst bei älteren Versionen in einer Zeile.
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")


def _add(zf: zipfile.ZipFile, name: str, data: bytes, compress: bool) -> None:
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def build_package(
    game_dir: Path,
    language: str,
    repo_root: Path,
    out_dir: Path,
    version: str | None = None,
) -> PackageResult:
    game_dir, repo_root, out_dir = Path(game_dir), Path(repo_root), Path(out_dir)
    version = version or mod_version(repo_root)
    missing = [rel for rel in LIBRARIES if not (game_dir / rel).is_file()]
    if missing:
        raise ValueError(
            f"Im Spielordner fehlt: {', '.join(missing)} (Mod mit -p:DeployToGame=true bauen)"
        )
    audio_rel = f"Mods/DrovaVoice/Audio/{language}"
    audio_dir = game_dir / audio_rel
    files, entries = indexed_audio(audio_dir)
    templates = repo_root / "release"
    values = {
        "version": version,
        "language": language,
        "entries": f"{entries:,}".replace(",", "."),
        "voices": voice_credits(repo_root / "casting" / "fish_voices.yaml"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"DrovaVoice-{version}-{language}.zip"
    part = target.with_name(target.name + ".part")
    with zipfile.ZipFile(part, "w") as zf:
        for name in TEXTS:
            _add(zf, name, _text(templates / name, values), compress=True)
        for rel in LIBRARIES:
            _add(zf, rel, (game_dir / rel).read_bytes(), compress=True)
        _add(zf, f"{audio_rel}/index.json", (audio_dir / "index.json").read_bytes(), compress=True)
        for rel in files:
            # OGG ist schon komprimiert; Speichern spart Zeit und kostet nichts.
            _add(zf, f"{audio_rel}/{rel}", (audio_dir / rel).read_bytes(), compress=False)
    part.replace(target)
    sha = hashlib.sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    digest = sha.hexdigest()
    target.with_name(target.name + ".sha256").write_text(
        f"{digest}  {target.name}\n", encoding="utf-8"
    )
    return PackageResult(target, digest, len(files), entries, target.stat().st_size)
