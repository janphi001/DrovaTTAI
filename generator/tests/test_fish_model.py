from datetime import date

from drova_voice.fish_model import (DEFAULT_FISH_MODEL, HISTORICAL_CACHE_MODEL, free_tier_warning, guard_fish_model,
                                    resolve_fish_profile, write_model_stamp)


def _profile(**kw):
    base = dict(language="de", model=None, latency=None, temperature=None, top_p=None, env={})
    base.update(kw)
    return resolve_fish_profile(base.pop("language"), base.pop("model"), base.pop("latency"),
                                base.pop("temperature"), base.pop("top_p"), base.pop("env"))


def test_defaults_and_env_override():
    profile = _profile()
    assert profile.model_id == DEFAULT_FISH_MODEL
    assert profile.params() == {"language": "de", "latency": "normal", "temperature": 0.7, "top_p": 0.7}
    assert profile.stamp().startswith("fish-audio/s2.1-pro-free language=de ")
    other = _profile(model="s2.1-pro", env={"FISH_TEMPERATURE": "0.4", "FISH_LATENCY": "low"})
    assert other.model_id == "s2.1-pro" and other.temperature == 0.4 and other.latency == "low"
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


def test_existing_cache_without_a_stamp_blocks_the_new_key_until_accepted(tmp_path):
    (tmp_path / "alt.wav").write_bytes(b"RIFF")
    profile = _profile()
    proceed, message = guard_fish_model(tmp_path, profile.stamp(), accept=False)
    assert not proceed and "Cache-Schlüssel" in message and "accept-model-change" in message
    assert HISTORICAL_CACHE_MODEL in message
    proceed, accepted = guard_fish_model(tmp_path, profile.stamp(), accept=True)
    assert proceed and "bestätigt" in accepted
    write_model_stamp(tmp_path, profile.stamp())
    again, quiet = guard_fish_model(tmp_path, profile.stamp(), accept=False)
    assert again and quiet == ""


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
