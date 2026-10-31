"""Release-Paket für Spieler: Mod, Bibliotheken, Audio und Liesmich in einem ZIP.

Quelle ist der Spielordner, also genau das, was im Spiel getestet wurde. Ins Paket kommen nur
OGG-Dateien, auf die `index.json` zeigt; verwaiste Dateien und der Export-Ordner bleiben draußen.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from drova_voice.config import _LANGUAGE_FOLDER
from drova_voice.encode import encode_one, find_tools, rel_audio_path
from drova_voice.ids import statement_id
from drova_voice.install import INDEX_VERSION, install_audio
from drova_voice.lines import Line
from drova_voice.player_name import GREETINGS

# Pfade relativ zum Spielordner, so landen sie auch im ZIP.
MOD_DLL = "Mods/DrovaVoice.dll"
CORE_DLL = "UserLibs/DrovaVoice.Core.dll"
NVORBIS_DLL = "UserLibs/NVorbis.dll"
LIBRARIES = (MOD_DLL, CORE_DLL, NVORBIS_DLL)
AUDIO_STAMP = "Mods/DrovaVoice/Audio/language.txt"
STUB_LIBRARY = b"drova-voice fixture stub\n"
FIXTURE_SPEECH = "The crate is empty."
FIXTURE_ID = statement_id("DT_Fixture", "Dialog/Crate", "Plh_1")
_FAKE_WORKER = Path(__file__).resolve().parents[1] / "workers" / "fake" / "worker.py"
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
    gap: Path


def mod_version(repo_root: Path) -> str:
    source = Path(repo_root) / "mod" / "DrovaVoice" / "DrovaVoiceMod.cs"
    match = _VERSION.search(source.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{source}: keine MelonInfo-Version gefunden")
    return match.group(1)


def _folder_code(language: object) -> str:
    if isinstance(language, str) and _LANGUAGE_FOLDER.fullmatch(language):
        return language
    raise ValueError(
        f"language = '{language}' ist kein gültiger Ordnername "
        "(erlaubt sind 1–16 Zeichen aus Buchstaben, Ziffern, '_' und '-')"
    )


def _safe_rel(rel: object) -> str | None:
    if not isinstance(rel, str) or not rel or "\\" in rel:
        return None
    path = PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    return path.as_posix()


def _load_indexed(audio_dir: Path, language: str) -> tuple[list[str], dict]:
    """Dateien aus index.json und die Einträge. Fehlt eine Datei, bricht es ab."""
    audio_dir = Path(audio_dir)
    index_path = audio_dir / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{index_path} fehlt (zuerst `drova-voice install`)") from None
    except json.JSONDecodeError as e:
        raise ValueError(f"{index_path}: kein gültiges JSON ({e})") from None
    if not isinstance(index, dict):
        raise ValueError(f"{index_path}: keine Einträge")
    version = index.get("version")
    # bool ist eine Unterklasse von int. True == 1 ist keine Index-Version.
    if isinstance(version, bool) or not isinstance(version, int) or version != INDEX_VERSION:
        raise ValueError(f"{index_path}: version {version!r} ist nicht {INDEX_VERSION}")
    got = index.get("language")
    if got != language:
        raise ValueError(f"{index_path}: language {got!r} passt nicht zu {language!r}")
    entries = index.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise ValueError(f"{index_path}: keine Einträge")
    files: set[str] = set()
    problems: list[str] = []
    for line_id, entry in entries.items():
        rel = _safe_rel(entry.get("file") if isinstance(entry, dict) else None)
        if rel is None:
            problems.append(f"{line_id}: ungültiger Pfad")
        elif not (audio_dir / rel).is_file():
            problems.append(f"{line_id}: {rel} fehlt")
        else:
            files.add(rel)
    if problems:
        shown = "; ".join(problems[:10])
        raise ValueError(f"{len(problems)} Einträge ohne Datei in {index_path}: {shown}")
    return sorted(files), entries


def indexed_audio(audio_dir: Path, language: str) -> tuple[list[str], int]:
    """Dateien aus index.json (sortiert, ohne Doppelte) und die Zahl der Einträge. Fehlt eine, bricht es ab."""
    files, entries = _load_indexed(audio_dir, language)
    return files, len(entries)


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


def entry_count_text(entries: int, language: str) -> str:
    """de gruppiert mit Punkt, jede andere Sprache mit Komma."""
    text = f"{entries:,}"
    if language == "de":
        return text.replace(",", ".")
    return text


def _readme_path(repo_root: Path, language: str) -> Path:
    name = "README.txt" if language == "de" else f"README.{language}.txt"
    path = Path(repo_root) / "release" / name
    if not path.is_file():
        raise ValueError(f"{path} fehlt")
    return path


def _origin_note(language: str, entry_ids: dict) -> str:
    if language != "en" or FIXTURE_ID in entry_ids:
        return ""
    return (
        "NOTE: EVERY VOICE IN THIS MOD IS AI-GENERATED.\n"
        "Fish Audio synthesized the lines. https://fish.audio\n"
        "No person recorded them.\n\n"
    )


def _readme_notes(language: str, entry_ids: dict, stub: bool) -> tuple[str, str]:
    if language != "en":
        return "", ""
    fixture = ""
    if FIXTURE_ID in entry_ids:
        fixture = (
            "The audio in this zip is a packaging fixture. "
            "The line is invented and is not Drova dialogue.\n"
            f'"{FIXTURE_SPEECH}"\n'
            "This zip is not the finished English voice set.\n\n"
        )
    library = ""
    if stub:
        library = (
            "The DLL bytes in this zip are stand-ins, not a MelonLoader mod. "
            "A shippable zip needs a build with -p:DeployToGame=true. "
            "That build supplies Mods/DrovaVoice.dll, "
            "UserLibs/DrovaVoice.Core.dll, and UserLibs/NVorbis.dll.\n\n"
        )
    return fixture, library


def _voice_regions(catalog: Path) -> set[str]:
    if not catalog.is_file():
        return set()
    raw = yaml.safe_load(catalog.read_text(encoding="utf-8")) or {}
    voices = raw.get("voices") if isinstance(raw, dict) else None
    found: set[str] = set()
    if isinstance(voices, dict):
        for voice in voices.values():
            if isinstance(voice, dict) and isinstance(voice.get("region"), str):
                found.add(voice["region"])
    return found


def _synth_gap(repo_root: Path, language: str, version: str, entries: int, entry_ids: dict) -> str:
    lines = [
        f"DrovaVoice {version}",
        f"language: {language}",
        f"entries: {entries}",
    ]
    if language == "en":
        if FIXTURE_ID in entry_ids:
            lines.append(FIXTURE_SPEECH)
        manifest = "data/export/en/manifest.json"
        state = "present" if (repo_root / manifest).is_file() else "absent"
        lines.append(f"{manifest} is {state}")
        if "en" in _voice_regions(repo_root / "casting" / "fish_voices.yaml"):
            lines.append("casting/fish_voices.yaml includes region en")
        else:
            lines.append("casting/fish_voices.yaml has no region en")
        lines.append("player_name greetings are German.")
        lines.append("player_name.GREETINGS: " + ", ".join(GREETINGS) + ".")
        lines.append(
            "The three ledgers are shared: data/lines.jsonl, "
            "data/synth/results.jsonl, and data/encoded.jsonl."
        )
        lines.append("Fish reads FISH_API_KEY from the environment.")
    return "\n".join(lines) + "\n"


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


def _library_bytes(game_dir: Path) -> list[tuple[str, bytes]]:
    missing = [rel for rel in LIBRARIES if not (game_dir / rel).is_file()]
    if missing:
        raise ValueError(
            f"Im Spielordner fehlt: {', '.join(missing)} (Mod mit -p:DeployToGame=true bauen)"
        )
    return [(rel, (game_dir / rel).read_bytes()) for rel in LIBRARIES]


def _place_libraries(staging: Path, libraries: Path | None) -> None:
    blobs = (
        [(rel, STUB_LIBRARY) for rel in LIBRARIES]
        if libraries is None
        else _library_bytes(libraries)
    )
    for rel, data in blobs:
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _call_fake_synth(text: str, wav: Path) -> None:
    # Der Fake-Worker hängt workers/_common vorne an sys.path. Das gilt nur für diesen Aufruf.
    name = "drova_fake_worker"
    saved = list(sys.path)
    try:
        module = sys.modules.get(name)
        if module is None:
            spec = importlib.util.spec_from_file_location(name, _FAKE_WORKER)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"{_FAKE_WORKER} fehlt")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        worker: Any = module
        worker.synth(None, {"text": text, "out_path": str(wav)})
    finally:
        sys.path[:] = saved


def _fixture_line() -> Line:
    return Line(
        id=FIXTURE_ID,
        tree="DT_Fixture",
        loca_path="Dialog/Crate",
        loca_key="Plh_1",
        node_type="statement",
        choice_index=None,
        actor="Crate",
        category="dialog",
        generic=False,
        raw=FIXTURE_SPEECH,
        speech=FIXTURE_SPEECH,
    )


def stage_fixture(repo_root: Path, language: str, libraries: Path | None) -> Path:
    """Spielordner unter out/fixture-<Sprache>/staging mit einer erfundenen Zeile."""
    language = _folder_code(language)
    repo_root = Path(repo_root)
    root = repo_root / "out" / f"fixture-{language}"
    if root.exists():
        shutil.rmtree(root)
    staging = root / "staging"
    work = root / "work"
    staging.mkdir(parents=True)
    _place_libraries(staging, None if libraries is None else Path(libraries))
    line = _fixture_line()
    wav = work / "clip.wav"
    wav.parent.mkdir(parents=True)
    _call_fake_synth(FIXTURE_SPEECH, wav)
    ffmpeg, ffprobe = find_tools()
    rel = rel_audio_path(line)
    ogg_root = work / "ogg"
    duration = encode_one(ffmpeg, ffprobe, wav, ogg_root / rel, (), line.id)
    install_dir = staging / "Mods" / "DrovaVoice" / "Audio" / language
    installed = install_audio(
        [{"id": line.id, "rel": rel, "duration": duration}],
        ogg_root,
        install_dir,
        language,
    )
    if installed.errors:
        raise ValueError("; ".join(installed.errors))
    return staging


def build_package(
    game_dir: Path,
    language: str,
    repo_root: Path,
    out_dir: Path,
    version: str | None = None,
) -> PackageResult:
    game_dir, repo_root, out_dir = Path(game_dir), Path(repo_root), Path(out_dir)
    language = _folder_code(language)
    version = version or mod_version(repo_root)
    library_bytes = _library_bytes(game_dir)
    audio_rel = f"Mods/DrovaVoice/Audio/{language}"
    audio_dir = game_dir / audio_rel
    files, entry_map = _load_indexed(audio_dir, language)
    entries = len(entry_map)
    stub = all(data == STUB_LIBRARY for _, data in library_bytes)
    fixture_note, library_note = _readme_notes(language, entry_map, stub)
    values = {
        "version": version,
        "language": language,
        "entries": entry_count_text(entries, language),
        "voices": voice_credits(repo_root / "casting" / "fish_voices.yaml"),
        "origin_note": _origin_note(language, entry_map),
        "fixture_note": fixture_note,
        "library_note": library_note,
    }
    readme = _text(_readme_path(repo_root, language), values)
    licenses = _text(repo_root / "release" / "LIZENZEN.txt", values)
    # Stempel kommt aus dem Sprachargument. Eine language.txt im Spielordner wird nicht kopiert.
    stamp = (language + "\n").encode("utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"DrovaVoice-{version}-{language}.zip"
    part = target.with_name(target.name + ".part")
    with zipfile.ZipFile(part, "w") as zf:
        _add(zf, "README.txt", readme, compress=True)
        _add(zf, "LIZENZEN.txt", licenses, compress=True)
        _add(zf, AUDIO_STAMP, stamp, compress=True)
        for rel, data in library_bytes:
            _add(zf, rel, data, compress=True)
        _add(
            zf,
            f"{audio_rel}/index.json",
            (audio_dir / "index.json").read_bytes(),
            compress=True,
        )
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
    gap = target.with_name(f"DrovaVoice-{version}-{language}.synth-gap.txt")
    gap.write_text(
        _synth_gap(repo_root, language, version, entries, entry_map),
        encoding="utf-8",
    )
    return PackageResult(target, digest, len(files), entries, target.stat().st_size, gap)
