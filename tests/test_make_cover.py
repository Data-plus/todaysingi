import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from scripts.make_cover import (
    CoverError,
    build_publish_cmd,
    extract_hook,
    parse_srt_hook,
    recommend_frame,
    score_frame,
    select_frame,
    thumb_offset_ms,
    validate_hook,
    wrap_text,
    write_metadata,
)


def make_frame(path: Path, *, black=False, subject=False):
    image = Image.new("RGB", (180, 320), "black" if black else (205, 210, 216))
    if subject:
        draw = ImageDraw.Draw(image)
        draw.rectangle((28, 52, 152, 265), fill=(244, 191, 39))
        draw.rectangle((46, 88, 134, 225), fill=(220, 45, 55))
        for x in range(48, 134, 12):
            draw.line((x, 88, x, 225), fill=(30, 80, 160), width=4)
    image.save(path)
    return path


def test_parse_srt_hook_uses_first_two_caption_blocks():
    text = """1
00:00:00,000 --> 00:00:01,000
열쇠고리인 줄 알았죠?

2
00:00:01,100 --> 00:00:02,000
진짜 찍히는 카메라예요.

3
00:00:02,100 --> 00:00:03,000
세 번째 문장입니다.
"""

    assert parse_srt_hook(text) == (
        "열쇠고리인 줄 알았죠?",
        "진짜 찍히는 카메라예요.",
    )


def test_extract_hook_falls_back_to_first_two_script_sentences(tmp_path):
    (tmp_path / "script.txt").write_text(
        "이게 키링인 줄 알았죠? 실제로 찍히는 카메라예요. 세 번째 설명입니다.",
        encoding="utf-8",
    )

    assert extract_hook(tmp_path) == (
        "이게 키링인 줄 알았죠?",
        "실제로 찍히는 카메라예요.",
    )


def test_extract_hook_prefers_srt_over_script(tmp_path):
    (tmp_path / "subs.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nSRT 첫 줄\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nSRT 둘째 줄\n",
        encoding="utf-8",
    )
    (tmp_path / "script.txt").write_text("대본 첫 문장. 대본 둘째 문장.", encoding="utf-8")

    assert extract_hook(tmp_path) == ("SRT 첫 줄", "SRT 둘째 줄")


@pytest.mark.parametrize("line1,line2", [("", "둘째"), ("첫째", ""), ("가" * 61, "둘째")])
def test_validate_hook_rejects_missing_or_excessive_copy(line1, line2):
    with pytest.raises(CoverError):
        validate_hook(line1, line2)


def test_frame_score_penalizes_black_space_and_rewards_clear_center_subject(tmp_path):
    black = make_frame(tmp_path / "black.jpg", black=True)
    clear = make_frame(tmp_path / "clear.jpg", subject=True)

    black_score = score_frame(black)
    clear_score = score_frame(clear)

    assert black_score["black_ratio"] > 0.95
    assert clear_score["black_ratio"] < 0.1
    assert clear_score["score"] > black_score["score"]


def test_recommend_frame_and_manual_override(tmp_path):
    candidates = [
        make_frame(tmp_path / "f01.jpg", black=True),
        make_frame(tmp_path / "f02.jpg", subject=True),
        make_frame(tmp_path / "f03.jpg"),
    ]

    recommended, scores = recommend_frame(candidates)

    assert recommended == 2
    assert scores["2"]["score"] > scores["1"]["score"]
    assert select_frame(candidates, recommended, override=3) == candidates[2]
    assert select_frame(candidates, recommended, override=None) == candidates[1]


def test_select_frame_rejects_missing_candidate(tmp_path):
    candidates = [make_frame(tmp_path / "f01.jpg", subject=True)]

    with pytest.raises(CoverError, match="프레임"):
        select_frame(candidates, recommended=1, override=6)


def test_wrap_text_respects_pixel_width_and_line_limit():
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 42)

    lines = wrap_text("엄지손가락만 한데 진짜 영상이 찍혀요", font, max_width=270, max_lines=3)

    assert 2 <= len(lines) <= 3
    assert all(font.getlength(line) <= 270 for line in lines)


def test_wrap_text_rejects_copy_that_needs_too_many_lines():
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 42)

    with pytest.raises(CoverError, match="줄"):
        wrap_text("가나다라마바사아자차카타파하" * 5, font, max_width=180, max_lines=2)


def test_publish_command_appends_cover_without_overwriting_final():
    command = build_publish_cmd("final.mp4", "cover.jpg", "publish.tmp.mp4", cover_seconds=0.5)
    joined = " ".join(command)

    assert command[0] == "ffmpeg"
    assert "final.mp4" in command
    assert "cover.jpg" in command
    assert "publish.tmp.mp4" == command[-1]
    assert "concat=n=2:v=1:a=0" in joined
    assert "apad=pad_dur=0.5" in joined
    assert "-loop 1" in joined


def test_thumb_offset_targets_middle_of_appended_cover():
    assert thumb_offset_ms(14.3, 0.5) == 14_550


def test_metadata_is_utf8_deterministic_and_contains_scores(tmp_path):
    path = tmp_path / "cover.json"
    metadata = {
        "version": 1,
        "selectedFrame": 2,
        "line1": "열쇠고리인 줄 알았죠?",
        "scores": {"2": {"score": 0.812345}},
    }

    write_metadata(path, metadata)

    assert json.loads(path.read_text(encoding="utf-8")) == metadata
    assert "열쇠고리" in path.read_text(encoding="utf-8")
    assert path.read_bytes().endswith(b"\n")
