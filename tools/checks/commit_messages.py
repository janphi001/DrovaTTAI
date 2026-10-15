#!/usr/bin/env python3
"""Fail when a commit message or a repo file carries a Claude commit trailer.

The plans used to end every commit with that trailer. Agents copy the nearest
example, so the example has to go, and a new commit that adds it has to fail.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = "co-authored-by"
MAIL = "noreply@" + "anthropic.com"


def has_trailer(text: str) -> bool:
    low = text.lower()
    if MAIL in low:
        return True
    start = 0
    while True:
        found = low.find(KEY, start)
        if found < 0:
            return False
        rest = low[found + len(KEY):]
        if rest.lstrip(" \t").startswith(":"):
            return True
        start = found + len(KEY)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False,
    )


def base_ref() -> str | None:
    override = os.environ.get("GITHUB_BASE_REF", "").strip()
    candidates = [f"origin/{override}"] if override else ["origin/main", "main"]
    for candidate in candidates:
        if git("rev-parse", "--verify", "--quiet", candidate).returncode == 0:
            return candidate
    return None


def tracked_files() -> list[str]:
    listed = git("ls-files", "-z")
    if listed.returncode != 0:
        return []
    return [name for name in listed.stdout.split("\0") if name]


def check_files() -> list[str]:
    errors: list[str] = []
    for name in tracked_files():
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if has_trailer(line):
                errors.append(
                    f"{name}:{number}: drop the Claude commit trailer. "
                    "Use an English imperative subject and do not add a Co-Authored-By line."
                )
    return errors


def check_subjects() -> list[str]:
    ref = base_ref()
    if ref is None:
        return []
    listed = git("rev-list", f"{ref}..HEAD")
    if listed.returncode != 0:
        return [f"commit_messages.py: cannot list commits from {ref}: {listed.stderr.strip()}"]
    errors: list[str] = []
    for sha in listed.stdout.split():
        shown = git("log", "-1", "--format=%s%n%b", sha)
        if shown.returncode != 0:
            errors.append(f"{sha}: cannot read the commit message")
            continue
        subject, _, body = shown.stdout.partition("\n")
        subject = subject.strip()
        if has_trailer(shown.stdout):
            errors.append(
                f"{sha[:12]}: drop the Claude commit trailer. "
                "Use an English imperative subject and do not add a Co-Authored-By line."
            )
            continue
        if not subject:
            errors.append(f"{sha[:12]}: write an English imperative subject")
        elif subject.endswith("."):
            errors.append(f"{sha[:12]}: drop the trailing period from the subject ({subject})")
        elif any(ord(char) > 127 for char in subject) or not subject[0].isupper():
            errors.append(
                f"{sha[:12]}: write an English imperative subject, for example 'Add the audio index'"
            )
        elif body and has_trailer(body):
            errors.append(f"{sha[:12]}: drop the Claude commit trailer from the body")
    return errors


def main() -> int:
    errors = check_files() + check_subjects()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"commit_messages.py: {len(errors)} trailer(s)", file=sys.stderr)
        return 1
    print("commit_messages.py: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
