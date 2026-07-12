import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from tts import (choose_engine, load_env, rate_to_tempo, to_words)


def test_load_env_parses_key_values(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# 주석\n"
        "TYPECAST_API_KEY=abc123\n"
        "\n"
        'QUOTED="hello world"\n'
        "SPACED = trimmed \n",
        encoding="utf-8")
    env = load_env(f)
    assert env["TYPECAST_API_KEY"] == "abc123"
    assert env["QUOTED"] == "hello world"
    assert env["SPACED"] == "trimmed"


def test_load_env_missing_file(tmp_path):
    assert load_env(tmp_path / "nope.env") == {}


def test_load_env_value_with_equals(tmp_path):
    f = tmp_path / ".env"
    f.write_text("KEY=a=b=c\n", encoding="utf-8")
    assert load_env(f)["KEY"] == "a=b=c"


def test_rate_to_tempo():
    assert rate_to_tempo("+0%") == 1.0
    assert rate_to_tempo("+10%") == 1.1
    assert rate_to_tempo("-20%") == 0.8


def test_rate_to_tempo_invalid():
    with pytest.raises(ValueError):
        rate_to_tempo("빠르게")


def test_to_words_maps_typecast_segments():
    api_words = [{"text": "신기한", "start": 0.08, "end": 0.38},
                 {"text": "물건", "start": 0.5, "end": 0.9}]
    words = to_words(api_words)
    assert words == [{"text": "신기한", "start_s": 0.08, "end_s": 0.38},
                     {"text": "물건", "start_s": 0.5, "end_s": 0.9}]
    assert to_words(None) == []


def test_choose_engine_prefers_typecast_when_key_exists():
    assert choose_engine("auto", api_key="abc") == "typecast"
    assert choose_engine("auto", api_key="") == "edge"
    assert choose_engine("edge", api_key="abc") == "edge"
    assert choose_engine("typecast", api_key="") == "typecast"
