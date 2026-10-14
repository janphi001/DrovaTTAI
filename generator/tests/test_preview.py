from drova_voice.emotions import EmotionTag
from drova_voice.lines import Line
from drova_voice.preview import write_preview


def line(key, speech="Zum Brunnen <bitte> & los.", actor="Mira", skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category="dialog", generic=False, raw=speech, speech="" if skip else speech, stage=(), skip=skip)


def test_preview_escapes_text_and_links_audio(tmp_path):
    audio = tmp_path / "audio"
    (audio / "dialog").mkdir(parents=True)
    (audio / "dialog" / "a.ogg").write_bytes(b"x")
    page = write_preview([line("Plh_1"), line("Plh_2", skip="gvar"), line("Plh_3")],
                         {"T|P|Plh_1": {"id": "T|P|Plh_1", "rel": "dialog/a.ogg", "duration": 1.0, "key": "k"}},
                         {"T|P|Plh_1": EmotionTag("sad", 0.5, source="llm")}, audio, tmp_path / "out" / "index.html", "Test <NPC>")
    html = page.read_text(encoding="utf-8")
    assert "Zum Brunnen &lt;bitte&gt; &amp; los." in html and "<bitte>" not in html
    assert "Test &lt;NPC&gt;" in html
    assert html.count("<audio") == 1 and "a.ogg" in html
    assert "sad 0.5" in html
    assert "übersprungen: gvar" in html and "noch nicht erzeugt" in html
