#!/usr/bin/env python3
"""Fail unless a mod build copies into the game only when asked.

`dotnet build mod/DrovaVoice -c Release` used to deploy on every successful
build. The supported deploy is `-p:DeployToGame=true`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSPROJ = ROOT / "mod" / "DrovaVoice" / "DrovaVoice.csproj"
OPT_IN = "'$(DeployToGame)' == 'true'"


def check_csproj(text: str, label: str) -> list[str]:
    match = re.search(r'<Target\b[^>]*\bName="DeployToGame"[^>]*>', text)
    if match is None:
        return [
            f"{label}: add an opt-in DeployToGame target. "
            "A plain dotnet build of mod/DrovaVoice must not copy into the game folder. "
            "Deploy with -p:DeployToGame=true."
        ]
    if OPT_IN not in match.group(0):
        return [
            f"{label}: DeployToGame runs on every build and copies into the game folder. "
            "Gate it with -p:DeployToGame=true."
        ]
    return []


def check_workflows(root: Path) -> list[str]:
    errors: list[str] = []
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return errors
    for path in sorted(workflow_dir.glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "dotnet build" not in line or "DrovaVoice" not in line:
                continue
            if "DrovaVoice.Core" in line and "DrovaVoice/" not in line and "DrovaVoice.csproj" not in line:
                continue
            errors.append(
                f"{path.relative_to(root)}:{number}: do not dotnet build mod/DrovaVoice in CI. "
                "That project copies into the game folder. Use dotnet test mod/DrovaVoice.Core.Tests."
            )
    return errors


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--csproj":
        path = Path(argv[1])
        errors = check_csproj(path.read_text(encoding="utf-8"), str(path))
    elif len(argv) == 0:
        errors = check_csproj(CSPROJ.read_text(encoding="utf-8"), str(CSPROJ.relative_to(ROOT)))
        errors.extend(check_workflows(ROOT))
    else:
        errors = ["usage: no_deploy_on_build.py [--csproj PATH]"]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"no_deploy_on_build.py: {len(errors)} problem(s)", file=sys.stderr)
        return 1
    print("no_deploy_on_build.py: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
