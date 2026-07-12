import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from publish_reel import (build_container_params, choose_offset,
                          mean_luminance, next_poll_action, public_video_url)


def test_public_video_url():
    assert public_video_url(1) == "https://todaysingi.netlify.app/media/1.mp4"
    assert public_video_url(12, base="https://example.com") == "https://example.com/media/12.mp4"


def test_build_container_params():
    p = build_container_params("https://x/v.mp4", "캡션 텍스트", "TOKEN")
    assert p["media_type"] == "REELS"
    assert p["video_url"] == "https://x/v.mp4"
    assert p["caption"] == "캡션 텍스트"
    assert p["access_token"] == "TOKEN"


def test_build_container_params_with_thumb_offset():
    p = build_container_params("https://x/v.mp4", "캡션", "TOKEN", thumb_offset_ms=4200)
    assert p["thumb_offset"] == 4200
    assert "thumb_offset" not in build_container_params("https://x/v.mp4", "캡션", "TOKEN")


def test_mean_luminance_bright_vs_dark(tmp_path):
    from PIL import Image
    bright = tmp_path / "b.jpg"
    dark = tmp_path / "d.jpg"
    Image.new("RGB", (10, 10), (240, 240, 240)).save(bright)
    Image.new("RGB", (10, 10), (10, 10, 10)).save(dark)
    assert mean_luminance(bright) > mean_luminance(dark)


def test_choose_offset_picks_brightest_timestamp():
    lums = [12.0, 180.5, 90.0]
    stamps_ms = [1000, 5000, 9000]
    assert choose_offset(lums, stamps_ms) == 5000
    assert choose_offset([], []) is None


def test_next_poll_action_transitions():
    assert next_poll_action("FINISHED", waited_s=10, timeout_s=300) == "publish"
    assert next_poll_action("IN_PROGRESS", waited_s=10, timeout_s=300) == "wait"
    assert next_poll_action("ERROR", waited_s=10, timeout_s=300) == "error"
    assert next_poll_action("EXPIRED", waited_s=10, timeout_s=300) == "error"
    assert next_poll_action("IN_PROGRESS", waited_s=301, timeout_s=300) == "error"
    assert next_poll_action("PUBLISHED", waited_s=10, timeout_s=300) == "publish"
