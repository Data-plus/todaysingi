import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from fetch_video import build_frames_cmd, build_mute_cmd, extract_mp4_urls


def test_extract_mp4_urls_from_ali_json_blob():
    html = (
        '{"videoUrl":"https:\\u002F\\u002Fvideo.aliexpress-media.com'
        '\\u002Fplay\\u002Fu\\u002F123.mp4","other":1}'
        '<script>var x = "https://cloud.video.taobao.com/play/u/456.mp4?auth=abc";</script>'
    )
    urls = extract_mp4_urls(html)
    assert "https://video.aliexpress-media.com/play/u/123.mp4" in urls
    assert "https://cloud.video.taobao.com/play/u/456.mp4?auth=abc" in urls


def test_extract_mp4_urls_dedupes_and_ignores_non_video():
    html = ('"https://a.com/v.mp4" "https://a.com/v.mp4" '
            '"https://a.com/image.jpg"')
    urls = extract_mp4_urls(html)
    assert urls == ["https://a.com/v.mp4"]


def test_extract_mp4_urls_empty():
    assert extract_mp4_urls("<html>no video here</html>") == []


def test_build_mute_cmd_copies_video_drops_audio():
    cmd = build_mute_cmd("raw.mp4", "muted.mp4")
    assert cmd[0] == "ffmpeg"
    assert "-an" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert cmd[-1] == "muted.mp4"


def test_build_frames_cmd_spreads_six_frames():
    cmd = build_frames_cmd("muted.mp4", 12.0, "frames/f%02d.jpg", count=6)
    joined = " ".join(cmd)
    assert "fps=6/12.0" in joined
    assert "-frames:v" in cmd and cmd[cmd.index("-frames:v") + 1] == "6"
    assert cmd[-1] == "frames/f%02d.jpg"
