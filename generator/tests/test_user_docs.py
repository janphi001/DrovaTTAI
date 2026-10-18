import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_readme_lists_every_preference_the_mod_creates():
    source = (ROOT / "mod" / "DrovaVoice" / "DrovaVoiceMod.cs").read_text(encoding="utf-8")
    keys = re.findall(r'CreateEntry\("([^"]+)"', source)
    assert keys
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    table = readme.split("Spielen und einstellen", 1)[1].split("## Verwendete Stimmen", 1)[0]
    missing = [key for key in keys if f"`{key}`" not in table]
    assert missing == []


def test_generator_doc_does_not_send_the_venv_to_setup():
    text = (ROOT / "docs" / "generator.md").read_text(encoding="utf-8")
    prerequisites = text.split("## Voraussetzungen", 1)[1].split("## Reihenfolge", 1)[0]
    assert "docs/setup.md" not in prerequisites
    assert "README" in prerequisites
    assert "manifest-loaded.json" in text
