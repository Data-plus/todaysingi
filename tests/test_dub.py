import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dub import (build_burn_cmd, build_mux_cmd, generate_srt,
                 recommended_chars, sec_to_timecode)


def word(text, start, end):
    return {"text": text, "start_s": start, "end_s": end}


def test_sec_to_timecode():
    assert sec_to_timecode(0) == "00:00:00,000"
    assert sec_to_timecode(61.32) == "00:01:01,320"
    assert sec_to_timecode(3661.005) == "01:01:01,005"


def test_generate_srt_single_block():
    words = [word("신기한", 0.0, 0.4), word("물건", 0.5, 0.9)]
    srt = generate_srt(words)
    assert "1\n00:00:00,000 --> 00:00:00,900\n신기한 물건" in srt


def test_generate_srt_splits_on_max_chars():
    words = [word("가나다라마바사", 0.0, 0.5), word("아자차카타파하", 0.6, 1.1),
             word("끝", 1.2, 1.4)]
    srt = generate_srt(words, max_chars=14)
    blocks = [b for b in srt.strip().split("\n\n") if b]
    assert len(blocks) == 2
    assert blocks[0].endswith("가나다라마바사")
    assert blocks[1].endswith("아자차카타파하 끝")


def test_generate_srt_splits_on_sentence_end():
    words = [word("좋아요.", 0.0, 0.5), word("다음", 0.6, 0.9)]
    srt = generate_srt(words, max_chars=50)
    blocks = [b for b in srt.strip().split("\n\n") if b]
    assert len(blocks) == 2


def test_generate_srt_empty():
    assert generate_srt([]) == ""


def test_recommended_chars():
    assert recommended_chars(10.0) == 50
    assert recommended_chars(14.6) == 73


def test_build_mux_cmd_no_reencode():
    cmd = build_mux_cmd("muted.mp4", "voice.mp3", "final.mp4")
    assert cmd[0] == "ffmpeg"
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
    assert "subtitles" not in " ".join(cmd)
    assert cmd[-1] == "final.mp4"


def test_build_burn_cmd_has_subtitles_filter():
    cmd = build_burn_cmd("muted.mp4", "voice.mp3", "subs.srt", "final.mp4")
    joined = " ".join(cmd)
    assert "subtitles=subs.srt" in joined
    assert "libx264" in joined
    assert "-shortest" in cmd
