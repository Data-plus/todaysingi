#!/usr/bin/env python3
"""완성된 릴스 영상을 Instagram Graph API로 게시한다.

사용 예:
    python scripts/publish_reel.py 1 --dry-run   # 호스팅·검증까지만
    python scripts/publish_reel.py 1             # 실제 게시

전제: .env에 INSTAGRAM_ACCOUNT_ID(IG 비즈니스 계정 ID), INSTAGRAM_ACCESS_TOKEN
(Facebook 사용자 토큰, instagram_content_publish 권한). 호스트는 graph.facebook.com.

흐름: final.mp4 → site/media/<id>.mp4 커밋·push(공개 URL 확보, Meta가 cURL로
가져가므로 필수) → 컨테이너 생성(REELS) → 처리 폴링 → 게시 → 관제탑 published.
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline
from tts import load_env

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = REPO_ROOT / "ops" / "assets"
MEDIA_DIR = REPO_ROOT / "site" / "media"
SITE_BASE = "https://todaysingi.netlify.app"
GRAPH = "https://graph.facebook.com/v21.0"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300


def public_video_url(item_id, base=SITE_BASE):
    return f"{base}/media/{item_id}.mp4"


def build_container_params(video_url, caption, token):
    return {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token,
    }


def next_poll_action(status_code, waited_s, timeout_s):
    if status_code in ("FINISHED", "PUBLISHED"):
        return "publish"
    if status_code in ("ERROR", "EXPIRED"):
        return "error"
    if waited_s > timeout_s:
        return "error"
    return "wait"


def host_video(item_id, final_mp4):
    """영상을 site/media/로 커밋·push하고 공개 URL이 살아날 때까지 대기."""
    import requests
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    dest = MEDIA_DIR / f"{item_id}.mp4"
    shutil.copyfile(final_mp4, dest)
    rel = dest.relative_to(REPO_ROOT).as_posix()
    subprocess.run(["git", "add", rel], cwd=REPO_ROOT, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if diff.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"feat: 릴스 영상 호스팅 [{item_id}]"],
                       cwd=REPO_ROOT, check=True)
        subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
    url = public_video_url(item_id)
    size = dest.stat().st_size
    print(f"배포 대기: {url} ({size:,} bytes)")
    for _ in range(60):
        try:
            r = requests.head(url, timeout=10)
            if r.status_code == 200 and int(r.headers.get("content-length", 0)) == size:
                print("호스팅 확인 완료")
                return url
        except requests.RequestException:
            pass
        time.sleep(5)
    raise RuntimeError("영상 URL이 시간 내에 활성화되지 않았습니다")


def create_container(ig_id, params):
    import requests
    r = requests.post(f"{GRAPH}/{ig_id}/media", data=params, timeout=60)
    body = r.json()
    if r.status_code != 200 or "id" not in body:
        raise RuntimeError(f"컨테이너 생성 실패: {body}")
    return body["id"]


def wait_until_ready(container_id, token):
    import requests
    waited = 0
    while True:
        r = requests.get(f"{GRAPH}/{container_id}",
                         params={"fields": "status_code", "access_token": token},
                         timeout=30)
        status = r.json().get("status_code", "UNKNOWN")
        action = next_poll_action(status, waited, POLL_TIMEOUT_S)
        print(f"  처리 상태: {status} ({waited}s)")
        if action == "publish":
            return
        if action == "error":
            raise RuntimeError(f"영상 처리 실패/시간초과: {status}")
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S


def publish_container(ig_id, container_id, token):
    import requests
    r = requests.post(f"{GRAPH}/{ig_id}/media_publish",
                      data={"creation_id": container_id, "access_token": token},
                      timeout=60)
    body = r.json()
    if r.status_code != 200 or "id" not in body:
        raise RuntimeError(f"게시 실패: {body}")
    return body["id"]


def get_permalink(media_id, token):
    import requests
    r = requests.get(f"{GRAPH}/{media_id}",
                     params={"fields": "permalink", "access_token": token},
                     timeout=30)
    return r.json().get("permalink", "")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="릴스를 Instagram API로 게시")
    parser.add_argument("id", type=int)
    parser.add_argument("--dry-run", action="store_true",
                        help="호스팅과 사전 검증까지만 하고 게시는 하지 않음")
    parser.add_argument("--skip-host", action="store_true",
                        help="이미 호스팅된 영상 URL을 재사용")
    args = parser.parse_args(argv)

    env = load_env()
    ig_id = env.get("INSTAGRAM_ACCOUNT_ID", "")
    token = env.get("INSTAGRAM_ACCESS_TOKEN", "")
    if not ig_id or not token:
        print(".env에 INSTAGRAM_ACCOUNT_ID / INSTAGRAM_ACCESS_TOKEN이 필요합니다",
              file=sys.stderr)
        return 1

    workdir = ASSETS_ROOT / str(args.id)
    final_mp4 = workdir / "final.mp4"
    caption_file = workdir / "caption.txt"
    if not final_mp4.exists():
        print(f"{final_mp4} 가 없습니다. dub.py 먼저.", file=sys.stderr)
        return 1
    if not caption_file.exists():
        print(f"{caption_file} 가 없습니다. 캡션 먼저.", file=sys.stderr)
        return 1
    caption = caption_file.read_text(encoding="utf-8").strip()

    url = public_video_url(args.id) if args.skip_host else host_video(args.id, final_mp4)

    if args.dry_run:
        print(f"\n[dry-run] 게시 준비 완료 — 영상: {url}")
        print(f"[dry-run] 캡션 {len(caption)}자, 계정 {ig_id}")
        print("[dry-run] 실제 게시: --dry-run 없이 재실행")
        return 0

    print("컨테이너 생성 중...")
    container = create_container(ig_id, build_container_params(url, caption, token))
    print(f"컨테이너: {container} — 영상 처리 대기")
    wait_until_ready(container, token)
    media_id = publish_container(ig_id, container, token)
    permalink = get_permalink(media_id, token)
    print(f"게시 완료! {permalink or media_id}")

    data = pipeline.load_data(pipeline.DEFAULT_FILE)
    pipeline.advance_item(data, args.id, to="published",
                          sets={"reelUrl": permalink, "igMediaId": media_id})
    pipeline.save_data(pipeline.DEFAULT_FILE, data)
    print(f"관제탑: [{args.id}] → 릴스게시(published)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
