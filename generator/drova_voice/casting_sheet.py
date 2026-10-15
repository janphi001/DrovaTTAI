from __future__ import annotations

import html
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.assign import mismatch
from drova_voice.casting import Casting
from drova_voice.fish_voices import Candidate
from drova_voice.lines import Line
from drova_voice.profiles import LOW_CONFIDENCE, Profile
from drova_voice.selection import SpeakerStat

_STYLE = ("body{font:15px system-ui;margin:2rem auto;max-width:75rem;padding:0 1rem}"
          "tr:nth-child(even){background:#8881}td{padding:.4rem .6rem;vertical-align:top}"
          ".who{white-space:nowrap;font-weight:600}.meta{color:#888;font-size:.85em}.flag{color:#c60;font-size:.85em}")


def write_casting_sheet(stats: Sequence[SpeakerStat], casting: Casting, candidates: Sequence[Candidate],
                        profiles: Mapping[str, Profile], samples: Mapping[str, Line], encoded: Mapping[str, dict],
                        audio_dir: Path, out_path: Path) -> Path:
    """Hörseite zur Abnahme der Besetzung: je Sprecher Steckbrief, Stimme und eine Beispielzeile."""
    esc = html.escape
    cand = {c.key: c for c in candidates}
    rows = []
    for s in sorted(stats, key=lambda s: (-s.lines, s.name)):
        profile = profiles.get(s.name)
        voice = casting.speakers.get(s.name)
        flags = []
        if profile is None:
            flags.append("kein Steckbrief")
        elif profile.confidence < LOW_CONFIDENCE:
            flags.append(f"unsicher ({profile.confidence:.1f})")
        if voice is None:
            flags.append("keine Stimme")
        elif profile is not None and voice in cand and (why := mismatch(profile, cand[voice])):
            flags.append(why)
        origin = "" if voice is None else ("auto" if s.name in casting.auto else "fest")
        bio = "" if profile is None else (f"{profile.gender}, {profile.age}" + (f", {profile.type}" if profile.type else "")
                                          + (f"<div class='meta'>{esc(profile.note)}</div>" if profile.note else ""))
        line = samples.get(s.name)
        row = encoded.get(line.id) if line else None
        if row and (Path(audio_dir) / row["rel"]).is_file():
            audio = f'<audio controls preload="none" src="{esc((Path(audio_dir) / row["rel"]).resolve().as_uri())}"></audio>'
        else:
            audio = "<span class='meta'>noch kein Ton</span>"
        text = esc(line.speech) if line else ""
        rows.append(
            f"<tr><td class='who'>{esc(s.display)}<div class='meta'>{s.lines} Zeilen</div></td><td>{bio}</td>"
            f"<td>{esc(voice or '-')}<div class='meta'>{origin}</div></td>"
            f"<td>{audio}<div class='meta'>{text}</div></td>"
            f"<td class='flag'>{esc('; '.join(flags))}</td></tr>")
    page = (f"<!doctype html><meta charset='utf-8'><title>Besetzung</title><style>{_STYLE}</style><h1>Besetzung</h1>"
            "<p class='meta'>Korrekturen in casting/casting.yaml: <code>name: {voice: schlüssel}</code> (gewinnt gegen casting_auto.yaml).</p>"
            "<table><tr><th>Sprecher</th><th>Steckbrief</th><th>Stimme</th><th>Beispiel</th><th>Hinweis</th></tr>"
            f"{''.join(rows)}</table>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path
