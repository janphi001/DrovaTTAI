#!/usr/bin/env python3
"""Fail when a change adds a dialogue line that was removed from the tests.

Commit e5086c8 took real lines out of generator/tests/test_loc.py. The same
lines stayed in the plan and in two tests this change cannot edit. The check
allows those existing copies and fails when a diff adds another one.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (length, sha256) of lines removed in e5086c8, plus two copies that survived.
# The plaintext stays out of this file.
BANNED = (
    (10, "669577eef1191c121593d1db6a93b8a89dd3f9dcf861358b2946443bc0fdb181"),
    (20, "1ac6df2f026407154d2b20cf0abe33b0363643ecdedb7f544a8631aef9618cd2"),
    (23, "32a4fb30cc0038fa31e47ebdb0c03499f52adaa482a96b8fd6474ce6be2b8c0e"),
    (26, "465331a9db76e1776498f48e13e6515e81a2adfd530615337136b5b900293c72"),
    (27, "ff9d1260442a200752a5edc51a495b57a257a7c6bef7f3ce5c3c2b4dcbf0ea46"),
    (33, "c14c574f479e8bb56c23284a933fe8161ec3f486aab0bb5bff9295e971e1d211"),
    (37, "aa1dee4b5aeb90c6d6e680e129861013beaf06ebcdca602f92c6699a7c6be5bf"),
    (39, "e5ac2c393768b6f8bd40c0c0986f76cfdb65c585b01cc94747afe93355f63a0d"),
)
HASHES = {digest for _, digest in BANNED}
LENGTHS = sorted({length for length, _ in BANNED})


def hits(text: str) -> set[str]:
    found: set[str] = set()
    if len(text) < min(LENGTHS):
        return found
    for length in LENGTHS:
        if length > len(text):
            continue
        for index in range(len(text) - length + 1):
            digest = hashlib.sha256(text[index:index + length].encode()).hexdigest()
            if digest in HASHES:
                found.add(digest)
                if len(found) == len(HASHES):
                    return found
    return found


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )


def base_ref() -> str | None:
    override = os.environ.get("GITHUB_BASE_REF", "").strip()
    candidates = [f"origin/{override}"] if override else ["origin/main", "main"]
    for candidate in candidates:
        if git("rev-parse", "--verify", "--quiet", candidate).returncode == 0:
            return candidate
    return None


def added_lines(diff: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            rows.append((current, line[1:]))
    return rows


def report(path: str, found: set[str]) -> str:
    return (
        f"{path}: quoted text matches a dialogue line removed in e5086c8. "
        "Use a short invented fixture, as in generator/tests/test_loc.py "
        f"(match {sorted(item[:12] for item in found)})."
    )


def check_diff(ref: str) -> list[str]:
    compared = git("diff", "-U0", ref)
    if compared.returncode != 0:
        return [f"no_game_dialogue.py: cannot diff against {ref}: {compared.stderr.strip()}"]
    errors: list[str] = []
    by_file: dict[str, set[str]] = {}
    for path, line in added_lines(compared.stdout):
        found = hits(line)
        if found:
            by_file.setdefault(path or "<diff>", set()).update(found)
    untracked = git("ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode == 0:
        for name in untracked.stdout.split("\0"):
            if not name:
                continue
            path = ROOT / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeError, OSError):
                continue
            found = hits(text)
            if found:
                by_file.setdefault(name, set()).update(found)
    for path, found in sorted(by_file.items()):
        errors.append(report(path, found))
    return errors


def check_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        return [f"{path}: cannot read ({exc})"]
    found = hits(text)
    if not found:
        return []
    return [report(str(path), found)]


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--file":
        errors = check_file(Path(argv[1]))
    elif len(argv) == 0:
        ref = base_ref()
        if ref is None:
            return _finish(["no_game_dialogue.py: no main ref to diff against"])
        errors = check_diff(ref)
    else:
        return _finish(["usage: no_game_dialogue.py [--file PATH]"])
    return _finish(errors)


def _finish(errors: list[str]) -> int:
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"no_game_dialogue.py: {len(errors)} file(s)", file=sys.stderr)
        return 1
    print("no_game_dialogue.py: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
