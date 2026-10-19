from datetime import date

from drova_voice.fish_model import (
    DEFAULT_FISH_MODEL,
    HISTORICAL_CACHE_MODEL,
    free_tier_warning,
    guard_fish_model,
    resolve_fish_profile,
    write_model_stamp,
)


def _profile(**kw):
    base = {
        "language": "de",
        "model": None,
        "latency": None,
        "temperature": None,
        "top_p": None,
        "env": {},
    }
    base.update(kw)
    return resolve_fish_profile(
        base.pop("language"),
        base.pop("model"),
        base.pop("latency"),
        base.pop("temperature"),
        base.pop("top_p"),
        base.pop("env"),
    )


def test_defaults_and_env_override():
    profile = _profile()
    assert profile.model_id == DEFAULT_FISH_MODEL
    # Standard = womit der vorhandene Cache entstand: nichts zusätzlich im Schlüssel
    assert profile.params() == {}
    assert profile.stamp() == HISTORICAL_CACHE_MODEL
    other = _profile(model="s2.1-pro", env={"FISH_TEMPERATURE": "0.4", "FISH_LATENCY": "low"})
    assert other.model_id == "s2.1-pro" and other.temperature == 0.4 and other.latency == "low"
    assert other.params() == {"latency": "low", "temperature": 0.4}
    assert other.stamp() == "fish-audio/s2.1-pro latency=low temperature=0.4"
    assert other.worker_env()["FISH_LANGUAGE"] == "de"


def test_unknown_model_and_bad_sampling_are_rejected():
    try:
        _profile(model="s2-free")
    except ValueError as e:
        assert "Unbekanntes Fish-Modell" in str(e)
    else:
        raise AssertionError("unbekanntes Modell")
    try:
        _profile(env={"FISH_TOP_P": "2"})
    except ValueError as e:
        assert "FISH_TOP_P" in str(e)
    else:
        raise AssertionError("top_p")


def test_existing_cache_without_a_stamp_stays_valid_for_the_default_profile(tmp_path):
    (tmp_path / "alt.wav").write_bytes(b"RIFF")
    proceed, message = guard_fish_model(tmp_path, _profile().stamp(), accept=False)
    assert proceed and message == ""


def test_existing_cache_without_a_stamp_blocks_a_changed_profile_until_accepted(tmp_path):
    (tmp_path / "alt.wav").write_bytes(b"RIFF")
    profile = _profile(env={"FISH_TEMPERATURE": "0.4"})
    proceed, message = guard_fish_model(tmp_path, profile.stamp(), accept=False)
    assert not proceed and "Cache-Schlüssel" in message and "accept-model-change" in message
    assert HISTORICAL_CACHE_MODEL in message
    proceed, accepted = guard_fish_model(tmp_path, profile.stamp(), accept=True)
    assert proceed and "bestätigt" in accepted
    write_model_stamp(tmp_path, profile.stamp())
    again, quiet = guard_fish_model(tmp_path, profile.stamp(), accept=False)
    assert again and quiet == ""


def test_default_profile_keeps_the_historical_cache_key():
    from drova_voice.synth import make_key

    old = make_key("fish", HISTORICAL_CACHE_MODEL, "voice-1", "Ein kurzer Satz.", {})
    profile = _profile()
    assert (
        make_key("fish", profile.cache_model(), "voice-1", "Ein kurzer Satz.", {**profile.params()})
        == old
    )


def test_sampling_change_is_its_own_cache_change(tmp_path):
    current = _profile().stamp()
    write_model_stamp(tmp_path, current)
    (tmp_path / "a.wav").write_bytes(b"RIFF")
    changed = _profile(temperature=0.5).stamp()
    proceed, message = guard_fish_model(tmp_path, changed, accept=False)
    assert not proceed and "temperature=0.5" in message


def test_switching_to_the_paid_model_names_the_price(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"RIFF")
    _, message = guard_fish_model(tmp_path, _profile(model="s2.1-pro").stamp(), accept=False)
    assert "15 USD" in message


def test_empty_cache_does_not_warn_and_the_free_tier_warning_follows_the_date(tmp_path):
    proceed, message = guard_fish_model(tmp_path / "leer", _profile().stamp(), accept=False)
    assert proceed and message == ""
    assert free_tier_warning(DEFAULT_FISH_MODEL, date(2026, 11, 30)) is None
    assert "30.11.2026" in free_tier_warning(DEFAULT_FISH_MODEL, date(2026, 12, 1))
    assert free_tier_warning("s2.1-pro", date(2026, 12, 1)) is None


def test_game_folder_zh_cn_becomes_a_bcp47_tag():
    assert _profile(language="zh_CN").language == "zh-CN"
