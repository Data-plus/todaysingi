#!/usr/bin/env python3
"""Instagram(Facebook) 액세스 토큰을 60일 장기 토큰으로 교환한다.

사용 예:
    python scripts/token_tool.py refresh   # .env의 토큰을 장기 토큰으로 교환·저장
    python scripts/token_tool.py info      # 현재 토큰의 만료 시각 확인

전제: .env에 INSTAGRAM_ACCESS_TOKEN(유효한 토큰), META_APP_ID, META_APP_SECRET.
대시보드에서 받은 단기 토큰(1시간)은 만료 전에 refresh를 실행해야 한다.
장기 토큰(60일)도 만료 전 refresh로 다시 60일 연장 가능.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import ENV_FILE, load_env

GRAPH = "https://graph.facebook.com/v21.0"


def set_env_key(path, key, value):
    """`.env`에서 key를 교체(없으면 추가). 다른 줄·주석은 보존."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def exchange_token(short_token, app_id, app_secret):
    import requests
    r = requests.get(f"{GRAPH}/oauth/access_token",
                     params={"grant_type": "fb_exchange_token",
                             "client_id": app_id,
                             "client_secret": app_secret,
                             "fb_exchange_token": short_token},
                     timeout=30)
    body = r.json()
    if "access_token" not in body:
        raise RuntimeError(f"교환 실패: {body.get('error', body)}")
    return body["access_token"], body.get("expires_in")


def token_info(token, app_id, app_secret):
    import requests
    r = requests.get(f"{GRAPH}/debug_token",
                     params={"input_token": token,
                             "access_token": f"{app_id}|{app_secret}"},
                     timeout=30)
    return r.json().get("data", {})


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    import datetime as dt

    parser = argparse.ArgumentParser(description="토큰 교환/확인")
    parser.add_argument("command", choices=["refresh", "info"])
    args = parser.parse_args(argv)

    env = load_env()
    token = env.get("INSTAGRAM_ACCESS_TOKEN", "")
    app_id = env.get("META_APP_ID", "")
    app_secret = env.get("META_APP_SECRET", "")
    if not token or not app_id or not app_secret:
        print(".env에 INSTAGRAM_ACCESS_TOKEN, META_APP_ID, META_APP_SECRET이 "
              "모두 필요합니다.", file=sys.stderr)
        return 1

    if args.command == "refresh":
        new_token, expires_in = exchange_token(token, app_id, app_secret)
        set_env_key(ENV_FILE, "INSTAGRAM_ACCESS_TOKEN", new_token)
        days = f"{expires_in / 86400:.0f}일" if expires_in else "약 60일"
        print(f"장기 토큰으로 교환 완료 (유효기간 {days}). .env 갱신됨.")
        return 0

    info = token_info(token, app_id, app_secret)
    exp = info.get("expires_at")
    when = dt.datetime.fromtimestamp(exp).isoformat() if exp else "알 수 없음"
    print(f"유효: {info.get('is_valid')}, 만료: {when}, "
          f"타입: {info.get('type')}, 앱: {info.get('application')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
