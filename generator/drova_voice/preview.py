from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from pathlib import Path

from drova_voice.emotions import EmotionTag
from drova_voice.lines import Line

_STYLE = (
    "body{font:15px system-ui;margin:2rem auto;max-width:60rem;padding:0 1rem}"
    "tr:nth-child(even){background:#8881}td{padding:.4rem .6rem;vertical-align:top}"
    ".who{white-space:nowrap;font-weight:600}.meta{color:#888;font-size:.85em}"
)


def write_preview(
    lines: Sequence[Line],
    encoded: Mapping[str, dict],
    emotions: Mapping[str, EmotionTag],
    audio_dir: Path,
    out_path: Path,
    title: str,
) -> Path:
    esc = html.escape
    rows = []
    for line in lines:
        emo = emotions.get(line.id)
        meta = f"{emo.emotion} {emo.intensity:g}" if emo else "neutral"
        row = encoded.get(line.id)
        if line.skip:
            cell = f"<span class='meta'>übersprungen: {esc(line.skip)}</span>"
        elif row and (Path(audio_dir) / row["rel"]).is_file():
            cell = f'<audio controls preload="none" src="{esc((Path(audio_dir) / row["rel"]).resolve().as_uri())}"></audio>'
        else:
            cell = "<span class='meta'>noch nicht erzeugt</span>"
        text = line.speech or line.raw
        rows.append(
            f"<tr><td class='who'>{esc(line.actor)}<div class='meta'>{esc(meta)}</div></td>"
            f"<td>{esc(text)}<div class='meta'>{esc(line.id)}</div></td><td>{cell}</td></tr>"
        )
    page = (
        f"<!doctype html><meta charset='utf-8'><title>{esc(title)}</title><style>{_STYLE}</style>"
        f"<h1>{esc(title)}</h1><table>{''.join(rows)}</table>"
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path
