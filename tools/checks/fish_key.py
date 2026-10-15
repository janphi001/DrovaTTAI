#!/usr/bin/env python3
"""Fail if the Fish key can leak, or if a file stores one.

Commit 0d26cb8 truncated the error body before masking the key. Commit
c3f9153 still followed redirects, which forwards the Authorization header.
The key is read from the environment only inside the Fish worker.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "generator" / "workers" / "fish" / "worker.py"
URL = "api.fish." + "audio"
ASSIGN = re.compile(r"""FISH_API_KEY\s*=\s*(['"])(.*?)\1""", re.DOTALL)
ALLOWED_URL_PREFIXES = (
    "generator/workers/fish/worker.py",
    "README.md",
    "docs/",
)


def check_worker(text: str, label: str) -> list[str]:
    errors: list[str] = []
    if "e.read()[" in text:
        errors.append(
            f"{label}: mask the Fish response with _clean before truncating it. "
            "generator/workers/fish/worker.py must not slice e.read()."
        )
    if "urllib.request.urlopen" in text:
        errors.append(
            f"{label}: do not follow redirects with urllib.request.urlopen. "
            "Use _NoRedirect in generator/workers/fish/worker.py so the Fish key is not forwarded."
        )
    match = re.search(
        r"class _NoRedirect\(urllib\.request\.HTTPRedirectHandler\):(?P<body>.*?)(?=\n(?:class |def )|\Z)",
        text,
        re.DOTALL,
    )
    if match is None or "return None" not in match.group("body"):
        errors.append(
            f"{label}: add _NoRedirect.redirect_request that returns None. "
            "A redirect would forward the Fish key."
        )
    return errors


def _key_allowed(value: str) -> bool:
    if value == "" or value.startswith("dein-") or value.startswith("sk-test"):
        return True
    if any(char in value for char in "<> \t\r\n\\"):
        return True
    return len(value) < 20


def check_assignments(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        for match in ASSIGN.finditer(text):
            if _key_allowed(match.group(2)):
                continue
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"{rel}:{line}: do not write FISH_API_KEY into a file. "
                "The Fish worker reads it from the environment."
            )
        if URL in text and not rel.startswith(ALLOWED_URL_PREFIXES) and rel not in ALLOWED_URL_PREFIXES:
            errors.append(
                f"{rel}: do not call Fish from here. "
                "The only client is generator/workers/fish/worker.py."
            )
    return errors


def main(argv: list[str]) -> int:
    errors: list[str] = []
    if len(argv) == 2 and argv[0] == "--worker":
        path = Path(argv[1])
        errors.extend(check_worker(path.read_text(encoding="utf-8"), str(path)))
    elif not argv:
        errors.extend(check_worker(WORKER.read_text(encoding="utf-8"), WORKER.relative_to(ROOT).as_posix()))
    else:
        errors.append("usage: fish_key.py [--worker PATH]")
    if not argv or (len(argv) == 2 and argv[0] == "--worker"):
        errors.extend(check_assignments(ROOT))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"fish_key.py: {len(errors)} problem(s)", file=sys.stderr)
        return 1
    print("fish_key.py: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
