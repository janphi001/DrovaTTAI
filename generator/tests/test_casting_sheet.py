from drova_voice.casting import Casting
from drova_voice.casting_sheet import write_casting_sheet
from drova_voice.fish_voices import Candidate
from drova_voice.lines import Line
from drova_voice.profiles import Profile
from drova_voice.selection import SpeakerStat

CANDS = [
    Candidate("anna", "f", "mittel", None, False),
    Candidate("carl", "m", "mittel", None, False),
]


def sample(name, text):
    return Line(
        id=f"T|P|{name}",
        tree="T",
        loca_path="P",
        loca_key=name,
        node_type="statement",
        choice_index=None,
        actor=name.title(),
        category="dialog",
        generic=False,
        raw=text,
        speech=text,
        stage=(),
        skip=None,
    )


def test_sheet_lists_speakers_with_voice_origin_flags_and_audio(tmp_path):
    stats = [
        SpeakerStat("mira", "Mira", 30, 900, frozenset({"T"})),
        SpeakerStat("bo", "Bo", 3, 90, frozenset({"T"})),
        SpeakerStat("cy", "Cy", 2, 60, frozenset({"T"})),
    ]
    casting = Casting("carl", {"mira": "anna", "bo": "carl"}, frozenset({"bo"}))
    profiles = {
        "mira": Profile("mira", "f", "mittel", None, 0.9, "ruhig & klar", "llm"),
        "bo": Profile("bo", "m", "mittel", None, 0.3, "unsicher", "llm"),
    }
    audio = tmp_path / "audio"
    (audio / "dialog").mkdir(parents=True)
    (audio / "dialog" / "a.ogg").write_bytes(b"x")
    samples = {"mira": sample("mira", "Ein <Satz> zum Hören."), "bo": sample("bo", "Zweiter Satz.")}
    encoded = {"T|P|mira": {"rel": "dialog/a.ogg"}}
    page = write_casting_sheet(
        stats, casting, CANDS, profiles, samples, encoded, audio, tmp_path / "out" / "index.html"
    )
    html = page.read_text(encoding="utf-8")
    assert html.index("Mira") < html.index("Bo") < html.index("Cy")  # nach Zeilenzahl
    assert "<audio" in html and html.count("<audio") == 1
    assert "Ein &lt;Satz&gt; zum Hören." in html and "ruhig &amp; klar" in html
    assert "fest" in html and "auto" in html
    assert "unsicher (0.3)" in html and "kein Steckbrief" in html and "keine Stimme" in html


def test_sheet_flags_a_type_variant_on_a_plain_figure(tmp_path):
    stats = [SpeakerStat("bo", "Bo", 3, 90, frozenset({"T"}))]
    cands = [Candidate("riese", "m", "mittel", "riese", True)]
    page = write_casting_sheet(
        stats,
        Casting("riese", {"bo": "riese"}, frozenset()),
        cands,
        {"bo": Profile("bo", "m", "mittel", None, 0.9, "", "llm")},
        {},
        {},
        tmp_path,
        tmp_path / "index.html",
    )
    assert "Typ-Variante für gewöhnliche Figur" in page.read_text(encoding="utf-8")
