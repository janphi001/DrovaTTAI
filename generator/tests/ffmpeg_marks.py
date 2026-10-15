import shutil
import subprocess

import pytest


def _has_rubberband() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace").stdout
    return " rubberband " in out


needs_rubberband = pytest.mark.skipif(not _has_rubberband() or shutil.which("ffprobe") is None,
                                      reason="ffmpeg mit rubberband und ffprobe nicht installiert")
