import json
from pathlib import Path

import pytest

from drova_voice.ids import audio_filename, choice_id, statement_id, with_variant

VECTORS = Path(__file__).resolve().parents[2] / "tests" / "vectors" / "line_ids.json"


def load_vectors():
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", load_vectors(), ids=lambda v: v["expectedId"])
def test_vectors(v):
    if v["kind"] == "choice":
        line_id = choice_id(v["tree"], v["locaPath"], v["locaKey"], v["choiceIndex"])
    else:
        line_id = statement_id(v["tree"], v["locaPath"], v["locaKey"])
    full_id = with_variant(line_id, v["variant"])
    assert full_id == v["expectedId"]
    assert audio_filename(full_id) == v["expectedFile"]


def test_rejects_separator_in_parts():
    with pytest.raises(ValueError):
        statement_id("DT|X", "Dialog/A", "Plh_1")


@pytest.mark.parametrize(
    "tree, loca_path, loca_key",
    [
        ("", "Dialog/A", "Plh_1"),
        ("DT_X", "/", "Plh_1"),
        ("DT_X", "", "Plh_1"),
        ("DT_X", "Dialog/A", ""),
    ],
)
def test_rejects_empty_parts(tree, loca_path, loca_key):
    with pytest.raises(ValueError):
        statement_id(tree, loca_path, loca_key)
    with pytest.raises(ValueError):
        choice_id(tree, loca_path, loca_key, 0)


def test_rejects_negative_choice_index():
    with pytest.raises(ValueError):
        choice_id("DT_X", "Dialog/A", "Plh_1", -1)


def test_rejects_bad_variant():
    with pytest.raises(ValueError):
        with_variant("DT_X|Dialog/A|Plh_1", "a#b")


def test_empty_variant_is_noop():
    assert with_variant("DT_X|A|Plh_1", None) == "DT_X|A|Plh_1"
    assert with_variant("DT_X|A|Plh_1", "") == "DT_X|A|Plh_1"
