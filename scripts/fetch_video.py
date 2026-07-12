#!/usr/bin/env python3
"""알리익스프레스 상품 영상을 내려받아 무음화하고 대본용 프레임을 추출한다.

사용 예:
    python scripts/fetch_video.py 1 --ali-url "https://ko.aliexpress.com/item/100500123.html"
    python scripts/fetch_video.py 1 --file "C:/Downloads/video.mp4"   # 수동 폴백

산출: ops/assets/<id>/{raw.mp4, muted.mp4, frames/f01~06.jpg}
완료 시 관제탑 video_ready 갱신 + 대본 권장 글자수 안내.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline
from dub import recommended_chars

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = REPO_ROOT / "ops" / "assets"
FRAME_COUNT = 6
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

VIDEO_HOST_HINT = re.compile(r"\.mp4(\?[^\"'\\\s]*)?$", re.IGNORECASE)


def extract_mp4_urls(html):
    """페이지 소스에서 mp4 URL 후보를 추출한다(유니코드 이스케이프 복원, 중복 제거)."""
    text = html.replace("\\u002F", "/").replace("\\/", "/")
    candidates = re.findall(r"https://[^\"'\\\s]+?\.mp4(?:\?[^\"'\\\s]*)?", text)
    urls = []
    for u in candidates:
        if u not in urls:
            urls.append(u)
    return urls


def build_mute_cmd(src, out):
    return ["ffmpeg", "-y", "-i", src, "-c:v", "copy", "-an", out]


def build_frames_cmd(src, duration_s, out_pattern, count=FRAME_COUNT):
    return ["ffmpeg", "-y", "-i", src, "-vf", f"fps={count}/{duration_s}",
            "-frames:v", str(count), out_pattern]


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def download(url, dest, referer=None):
    import requests
    headers = {"User-Agent": MOBILE_UA}
    if referer:
        headers["Referer"] = referer
    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)


def obtain_raw(args, workdir):
    """전략 1~3 순서대로 시도해 raw.mp4를 확보한다. 성공 시 경로, 실패 시 None."""
    raw = workdir / "raw.mp4"

    if args.file:
        src = Path(args.file)
        if not src.exists():
            print(f"파일이 없습니다: {src}", file=sys.stderr)
            return None
        shutil.copyfile(src, raw)
        print(f"수동 파일 사용: {src}")
        return raw

    if not args.ali_url:
        print("--ali-url 또는 --file 중 하나가 필요합니다.", file=sys.stderr)
        return None

    print("전략 1: 페이지에서 영상 URL 추출 시도...")
    try:
        import requests
        r = requests.get(args.ali_url, headers={"User-Agent": MOBILE_UA}, timeout=30)
        urls = extract_mp4_urls(r.text)
        if urls:
            print(f"  후보 {len(urls)}건, 첫 번째 다운로드: {urls[0][:80]}...")
            download(urls[0], raw, referer=args.ali_url)
            return raw
        print("  영상 URL을 찾지 못했습니다.")
    except Exception as e:
        print(f"  실패: {e}")

    print("전략 2: yt-dlp 시도...")
    result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "-o", str(raw), "-f", "mp4/best",
         args.ali_url],
        capture_output=True, text=True)
    if result.returncode == 0 and raw.exists():
        return raw
    print(f"  실패: {result.stderr.strip()[-200:]}")
    return None


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="알리 영상 수집 → 무음화 → 프레임 추출")
    parser.add_argument("id", type=int)
    parser.add_argument("--ali-url", default=None)
    parser.add_argument("--file", default=None, help="수동 다운로드한 영상 파일 경로(폴백)")
    args = parser.parse_args(argv)

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe가 필요합니다. https://ffmpeg.org 설치 후 재실행하세요.",
              file=sys.stderr)
        return 1

    data = pipeline.load_data(pipeline.DEFAULT_FILE)
    if not any(i["id"] == args.id for i in data["items"]):
        print(f"관제탑에 id {args.id} 아이템이 없습니다. pipeline.py new 먼저.", file=sys.stderr)
        return 1

    workdir = ASSETS_ROOT / str(args.id)
    (workdir / "frames").mkdir(parents=True, exist_ok=True)

    raw = obtain_raw(args, workdir)
    if raw is None:
        print("\n영상을 자동으로 받지 못했습니다. 수동 폴백:", file=sys.stderr)
        print("  1) 브라우저에서 알리 상품 페이지 열기 → F12 → Network 탭 → 영상 재생", file=sys.stderr)
        print("  2) mp4 요청 우클릭 → 새 탭에서 열기 → 저장", file=sys.stderr)
        print(f"  3) python scripts/fetch_video.py {args.id} --file <저장경로> 재실행", file=sys.stderr)
        return 1

    muted = workdir / "muted.mp4"
    r = subprocess.run(build_mute_cmd(str(raw), str(muted)),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-500:], file=sys.stderr)
        return 1

    duration = probe_duration(muted)
    fr = subprocess.run(
        build_frames_cmd(str(muted), duration, str(workdir / "frames" / "f%02d.jpg")),
        capture_output=True, text=True)
    if fr.returncode != 0:
        print(fr.stderr[-500:], file=sys.stderr)
        return 1

    sets = {"mutedVideo": muted.relative_to(REPO_ROOT).as_posix()}
    if args.ali_url:
        sets["aliUrl"] = args.ali_url
    pipeline.advance_item(data, args.id, to="video_ready", sets=sets)
    pipeline.save_data(pipeline.DEFAULT_FILE, data)

    print(f"\n완료: {muted} ({duration:.1f}초), 프레임 {FRAME_COUNT}장")
    print(f"대본 권장 길이: 약 {recommended_chars(duration)}자 이내 (초당 {5}자 기준)")
    print(f"관제탑: [{args.id}] → 영상준비(video_ready)")
    print(f"다음: {workdir / 'frames'} 의 프레임을 보고 script.txt 작성")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
